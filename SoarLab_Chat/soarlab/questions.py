"""English intent/slot resolver. Classifies text outside Soar; never supplies factual answers.

This is a deterministic lexical + controlled-fuzzy parser, NOT generative language
understanding. Every substantive reply is produced from native Soar productions.
"""
from __future__ import annotations
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
PROCEDURES = json.loads((ROOT/'data'/'procedural_catalog.json').read_text(encoding='utf8'))
EP_TOPICS = {
    'obstacle': ('obstacle','collision','barrier','wall','bumper'),
    'battery': ('battery','recharge','charging','voltage','power'),
    'sensor': ('sensor','encoder','ultrasonic','imu','measurement'),
    'navigation': ('navigation','path','route','waypoint','localization'),
    'vision': ('vision','camera','image','detection','marker'),
    'actuator': ('actuator','motor','servo','gripper','joint'),
}
STOPWORDS = set('''what which when why how who where tell me explain describe define about the a an
please could would should can does do is are was were it this these that for of to in on at by
and with from my your robot robotics robotic system technology used use meaning function works
work know give information concept what s'''.split())

def fold(text):
    v=unicodedata.normalize('NFKD',str(text).lower())
    v=''.join(c for c in v if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^a-z0-9]+',' ',v).split())

def topic_key(text): return fold(text).replace(' ','-')[:90]

def aliases_for(item):
    return sorted({fold(v) for v in [item['label'],item['topic'].replace('-',' ')] + item.get('aliases',[]) if len(fold(v))>=2},key=len,reverse=True)

def matches_alias(q,alias):
    return bool(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',q))

def classify(question,facts):
    q=fold(question)
    if not q:return {'intent':'unknown','topic':'','method':'empty','confidence':0.0}
    # Explicit recall requests take precedence over semantic questions.
    episodic_cues=('remember','recall','previous experience','last time','earlier episode',
                   'what happened','experienced','past event','in the past','last episode',
                   'ever encountered','before')
    if any(matches_alias(q,v) for v in episodic_cues):
        for topic,keywords in EP_TOPICS.items():
            if any(matches_alias(q,k) for k in keywords):
                return {'intent':'episodic','topic':topic,'method':'episodic-cue','confidence':1.0}
        return {'intent':'episodic','topic':'navigation','method':'episodic-default','confidence':0.5}
    # Match specific scenario rules before any bare concept token (e.g. battery).
    procedure_candidates=[]
    for p in PROCEDURES:
        for variant in [p['question']]+p.get('aliases',[]):
            v=fold(variant)
            if q==v: procedure_candidates.append((10+len(v),p['topic'],'procedure-exact'))
    if procedure_candidates:
        _,topic,method=max(procedure_candidates)
        return {'intent':'procedural','topic':topic,'method':method,'confidence':1.0}
    # Six concise, commonly used procedural requests without scenario context.
    simple={
       'low-battery': ('battery is low','low battery','battery runs low','battery level is low'),
       'obstacle-close': ('obstacle is close','close obstacle','obstacle ahead','robot encounters an obstacle'),
       'sensor-failure': ('sensor fails','sensor failure','sensor stops responding'),
       'overheating': ('motor overheats','motor is overheating','hot motor'),
       'lost-localization': ('localization is lost','robot loses localization','lost robot localization'),
       'emergency-stop': ('emergency stop is triggered','press emergency stop','emergency stop activated'),
    }
    proc_cues=('what should','what to do','how should','procedure','how to react','which action','robot do','react when','respond when')
    if any(k in q for k in proc_cues):
        for topic,phrases in simple.items():
            if any(p in q for p in phrases):
                return {'intent':'procedural','topic':topic,'method':'procedure-cue','confidence':1.0}
    # Native SMem retrieval cue is selected externally; facts never returned from Python.
    candidates=[]
    for item in facts:
        for a in aliases_for(item):
            if matches_alias(q,a):
                candidates.append((len(a.split()),len(a),item['topic']))
    if candidates:
        _,_,topic=max(candidates,key=lambda x:(x[0],x[1]))
        return {'intent':'semantic','topic':topic,'method':'semantic-alias','confidence':1.0}
    # Explicit semantic descriptions, controlled and auditable (not free-form paraphrase).
    clues={
      'ultrasonic-sensor':('distance from a returning sound wave','distance by measuring echoes'),
      'pid-controller':('proportional integral derivative terms','proportional plus integral and derivative'),
      'slam':('mapping and localization simultaneously','map the world while locating itself'),
      'encoder':('rotational pulses on the wheels','wheel rotation pulses'),
      'odometry':('estimate distance from wheel motion',),
      'episodic-memory':('remember states from previous experiences',),
      'semantic-memory':('long term declarative facts',),
    }
    for topic,phrases in clues.items():
        if any(k in q for k in phrases):
            return {'intent':'semantic','topic':topic,'method':'controlled-paraphrase','confidence':0.96}
    # Fuzzy parsing is restricted to confident matches with a unique best score.
    content=[v for v in q.split() if v not in STOPWORDS and len(v)>2]
    if content:
        phrase=' '.join(content);scores=[]
        for item in facts:
            for alias in aliases_for(item):
                terms=[v for v in alias.split() if v not in STOPWORDS]
                if not terms:continue
                overlap=len(set(content)&set(terms))/max(len(set(content)),len(set(terms)))
                ratio=SequenceMatcher(None,phrase,alias).ratio()
                scores.append((max(overlap*.90,ratio*.88),item['topic']))
        ranked=sorted(scores,reverse=True)
        if ranked and ranked[0][0]>=.83:
            competing=max((s for s,t in ranked if t!=ranked[0][1]),default=0)
            if ranked[0][0]-competing>=.055:
                return {'intent':'semantic','topic':ranked[0][1],'method':'fuzzy','confidence':round(ranked[0][0],3)}
    # Unknown terms still query Soar SMem so the student can teach them.
    clean=q
    clean=re.sub(r'^(what is|what are|define|explain|tell me about|describe|how does|how do|what does|information about|do you know|what can you tell me about)\s+','',clean)
    clean=re.sub(r'^(the|a|an)\s+','',clean)
    return {'intent':'semantic','topic':topic_key(clean),'method':'unknown-concept','confidence':0.0}

# Independent reference topics for this deterministic closed-domain question set.
# Variants were authored as a controlled test corpus. Do not claim zero-shot generalization.
PARAPHRASE_TESTS=[
 ('What is an ultrasonic sensor?','semantic','ultrasonic-sensor'),
 ('Explain the ultrasonic rangefinder.','semantic','ultrasonic-sensor'),
 ('How do robots use a LiDAR sensor?','semantic','lidar-sensor'),
 ('Tell me about the laser scanner.','semantic','lidar-sensor'),
 ('What is simultaneous localization and mapping?','semantic','slam'),
 ('Explain SLAM.','semantic','slam'),
 ('What is a servo motor?','semantic','servomotor'),
 ('Explain the role of a servomotor.','semantic','servomotor'),
 ('What is a PID controller?','semantic','pid-controller'),
 ('Describe proportional integral derivative terms.','semantic','pid-controller'),
 ('Describe the NAO humanoid.','semantic','nao-robot'),
 ('What is the NAO robot?','semantic','nao-robot'),
 ('Explain Soar semantic memory.','semantic','semantic-memory'),
 ('What does SMem store?','semantic','semantic-memory'),
 ('What is a depth camera?','semantic','depth-camera'),
 ('Tell me about the depth sensor.','semantic','depth-camera'),
 ('What does a wheel encoder do?','semantic','encoder'),
 ('Explain rotary encoders.','semantic','encoder'),
 ('What is the purpose of ROS 2?','semantic','ros-2'),
 ('Explain the Robot Operating System 2.','semantic','ros-2'),
 ('What is an occupancy grid?','semantic','occupancy-grid'),
 ('Explain grid map.','semantic','occupancy-grid'),
 ('What is a robot gripper?','semantic','gripper'),
 ('Tell me about the robotic gripper.','semantic','gripper'),
 ('What should the robot do if the battery is low in a classroom demonstration?','procedural','low-battery'),
 ('How should the robot react when the battery is low in a classroom demonstration?','procedural','low-battery'),
 ('What should the robot do if an obstacle is close in a classroom demonstration?','procedural','obstacle-close'),
 ('How should the robot react when an obstacle is close in a classroom demonstration?','procedural','obstacle-close'),
 ('What should the robot do if a sensor fails in a classroom demonstration?','procedural','sensor-failure'),
 ('How should the robot react when a sensor fails in a classroom demonstration?','procedural','sensor-failure'),
 ('What should the robot do if the emergency stop is triggered in a classroom demonstration?','procedural','emergency-stop'),
 ('How should the robot react when the emergency stop is triggered in a classroom demonstration?','procedural','emergency-stop'),
 ('What should the robot do if localization is lost in a classroom demonstration?','procedural','lost-localization'),
 ('How should the robot react when localization is lost in a classroom demonstration?','procedural','lost-localization'),
 ('What should the robot do if a motor overheats in a classroom demonstration?','procedural','overheating'),
 ('How should the robot react when a motor overheats in a classroom demonstration?','procedural','overheating'),
 ('Do you remember an obstacle?','episodic','obstacle'),
 ('What happened with an obstacle before?','episodic','obstacle'),
 ('Do you remember a low battery episode?','episodic','battery'),
 ('What happened with the battery earlier?','episodic','battery'),
 ('Do you remember a sensor experience?','episodic','sensor'),
 ('What happened to a sensor before?','episodic','sensor'),
 ('Do you remember an earlier navigation episode?','episodic','navigation'),
 ('What happened during navigation before?','episodic','navigation'),
 ('Do you remember a camera event?','episodic','vision'),
 ('What happened to the camera earlier?','episodic','vision'),
 ('Do you remember a motor experience?','episodic','actuator'),
 ('What happened to the motor before?','episodic','actuator'),
]
EXAMPLES=[
 ('Semantic','What is the NAO robot?'),('Semantic','What is ROS 2?'),
 ('Semantic','Explain LiDAR sensor.'),('Semantic','What is an occupancy grid?'),
 ('Procedural','What should the robot do if the battery is low in a classroom demonstration?'),
 ('Procedural','What should the robot do if an obstacle is close in a classroom demonstration?'),
 ('Procedural','What should the robot do if the emergency stop is triggered in a classroom demonstration?'),
 ('Episodic','Do you remember an obstacle?'),('Episodic','What happened with the battery earlier?'),
 ('Episodic','Do you remember a camera event?'),
 ('Teach','What is a tactile sensor array?'),('Teach','Explain a robot swarm controller.'),
]
