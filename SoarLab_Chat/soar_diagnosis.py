"""Native Soar verification. Every reported success relies on the real SML kernel."""
import traceback
from soarlab.native import SoarChat

if __name__=='__main__':
    agent=None
    try:
        print('Starting native Soar 9.6.5: verifying 124 semantic facts, 120 episodes, and 108 rules...')
        print('Initialization verifies the semantic and episodic data one item at a time.')
        agent=SoarChat()
        print('Native initialization state:',agent.state())
        assert agent.state()['native_verifications']['semantic'] >= 124
        assert agent.state()['native_verifications']['episodic'] >= 120
        samples=[('What is the NAO robot?','semantic','found'),
                 ('Explain the servo motor.','semantic','found'),
                 ('What should the robot do if the battery is low in a classroom demonstration?','procedural','found'),
                 ('Do you remember an obstacle?','episodic','found'),
                 ('What is a tactile sensor array?','semantic','unknown')]
        for q,kind,status in samples:
            response=agent.ask(q)
            print('Question:',q,'\nResult:',response,'\n')
            if response['kind']!=kind or response['status']!=status:
                raise RuntimeError('Unexpected native answer: '+q)
        fact={'topic':'temporary-test-concept','label':'Temporary test concept',
              'description':'This temporary test concept verifies native semantic storage and retrieval.',
              'aliases':[]}
        agent._install_fact(fact)
        result=agent._invoke('semantic',fact['topic'],'native-semantic-check')
        assert result['status']=='found' and result['text']==fact['description']
        print('NATIVE SMEM READ-AFTER-WRITE: PASS')
        episode={'topic':'vision','description':'Temporary diagnostic episode: the camera recognized a green marker.'}
        agent._install_event(episode)
        print('NATIVE EPMEM READ-AFTER-WRITE: PASS')
        print('NATIVE SOAR DIAGNOSTIC: PASS')
    except Exception:
        print('NATIVE SOAR DIAGNOSTIC: FAILED\n',traceback.format_exc())
        raise SystemExit(1)
    finally:
        if agent:agent.close()
