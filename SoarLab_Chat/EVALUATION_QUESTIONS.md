# Evaluation questions — English controlled-language test set

The fixed benchmark repeats exactly these 48 reference-labeled questions. Parser aliases and native memory retrieval are separate operations.

## Semantic

1. `What is an ultrasonic sensor?` — expected topic: `ultrasonic-sensor`
2. `Explain the ultrasonic rangefinder.` — expected topic: `ultrasonic-sensor`
3. `How do robots use a LiDAR sensor?` — expected topic: `lidar-sensor`
4. `Tell me about the laser scanner.` — expected topic: `lidar-sensor`
5. `What is simultaneous localization and mapping?` — expected topic: `slam`
6. `Explain SLAM.` — expected topic: `slam`
7. `What is a servo motor?` — expected topic: `servomotor`
8. `Explain the role of a servomotor.` — expected topic: `servomotor`
9. `What is a PID controller?` — expected topic: `pid-controller`
10. `Describe proportional integral derivative terms.` — expected topic: `pid-controller`
11. `Describe the NAO humanoid.` — expected topic: `nao-robot`
12. `What is the NAO robot?` — expected topic: `nao-robot`
13. `Explain Soar semantic memory.` — expected topic: `semantic-memory`
14. `What does SMem store?` — expected topic: `semantic-memory`
15. `What is a depth camera?` — expected topic: `depth-camera`
16. `Tell me about the depth sensor.` — expected topic: `depth-camera`
17. `What does a wheel encoder do?` — expected topic: `encoder`
18. `Explain rotary encoders.` — expected topic: `encoder`
19. `What is the purpose of ROS 2?` — expected topic: `ros-2`
20. `Explain the Robot Operating System 2.` — expected topic: `ros-2`
21. `What is an occupancy grid?` — expected topic: `occupancy-grid`
22. `Explain grid map.` — expected topic: `occupancy-grid`
23. `What is a robot gripper?` — expected topic: `gripper`
24. `Tell me about the robotic gripper.` — expected topic: `gripper`

## Procedural

25. `What should the robot do if the battery is low in a classroom demonstration?` — expected topic: `low-battery`
26. `How should the robot react when the battery is low in a classroom demonstration?` — expected topic: `low-battery`
27. `What should the robot do if an obstacle is close in a classroom demonstration?` — expected topic: `obstacle-close`
28. `How should the robot react when an obstacle is close in a classroom demonstration?` — expected topic: `obstacle-close`
29. `What should the robot do if a sensor fails in a classroom demonstration?` — expected topic: `sensor-failure`
30. `How should the robot react when a sensor fails in a classroom demonstration?` — expected topic: `sensor-failure`
31. `What should the robot do if the emergency stop is triggered in a classroom demonstration?` — expected topic: `emergency-stop`
32. `How should the robot react when the emergency stop is triggered in a classroom demonstration?` — expected topic: `emergency-stop`
33. `What should the robot do if localization is lost in a classroom demonstration?` — expected topic: `lost-localization`
34. `How should the robot react when localization is lost in a classroom demonstration?` — expected topic: `lost-localization`
35. `What should the robot do if a motor overheats in a classroom demonstration?` — expected topic: `overheating`
36. `How should the robot react when a motor overheats in a classroom demonstration?` — expected topic: `overheating`

## Episodic

37. `Do you remember an obstacle?` — expected topic: `obstacle`
38. `What happened with an obstacle before?` — expected topic: `obstacle`
39. `Do you remember a low battery episode?` — expected topic: `battery`
40. `What happened with the battery earlier?` — expected topic: `battery`
41. `Do you remember a sensor experience?` — expected topic: `sensor`
42. `What happened to a sensor before?` — expected topic: `sensor`
43. `Do you remember an earlier navigation episode?` — expected topic: `navigation`
44. `What happened during navigation before?` — expected topic: `navigation`
45. `Do you remember a camera event?` — expected topic: `vision`
46. `What happened to the camera earlier?` — expected topic: `vision`
47. `Do you remember a motor experience?` — expected topic: `actuator`
48. `What happened to the motor before?` — expected topic: `actuator`

## Additional native procedural scenario questions

These are available to students as extra demonstrations but are not all part of the fixed 48-item test corpus.

- `What should the robot do if the battery is low in a classroom demonstration?` (`low-battery`)
- `What should the robot do if the battery is low during corridor navigation?` (`low-battery-corridor`)
- `What should the robot do if the battery is low during a mapping mission?` (`low-battery-mapping`)
- `What should the robot do if the battery is low while docking?` (`low-battery-docking`)
- `What should the robot do if the battery is low during teleoperation?` (`low-battery-remote-control`)
- `What should the robot do if the battery is low during a laboratory bench test?` (`low-battery-test-bench`)
- `What should the robot do if an obstacle is close in a classroom demonstration?` (`obstacle-close`)
- `What should the robot do if an obstacle is close during corridor navigation?` (`obstacle-close-corridor`)
- `What should the robot do if an obstacle is close during a mapping mission?` (`obstacle-close-mapping`)
- `What should the robot do if an obstacle is close while docking?` (`obstacle-close-docking`)
- `What should the robot do if an obstacle is close during teleoperation?` (`obstacle-close-remote-control`)
- `What should the robot do if an obstacle is close during a laboratory bench test?` (`obstacle-close-test-bench`)
- `What should the robot do if the path is clear in a classroom demonstration?` (`obstacle-clear`)
- `What should the robot do if the path is clear during corridor navigation?` (`obstacle-clear-corridor`)
- `What should the robot do if the path is clear during a mapping mission?` (`obstacle-clear-mapping`)
- `What should the robot do if the path is clear while docking?` (`obstacle-clear-docking`)
- `What should the robot do if the path is clear during teleoperation?` (`obstacle-clear-remote-control`)
- `What should the robot do if the path is clear during a laboratory bench test?` (`obstacle-clear-test-bench`)
- `What should the robot do if localization is lost in a classroom demonstration?` (`lost-localization`)
- `What should the robot do if localization is lost during corridor navigation?` (`lost-localization-corridor`)
- `What should the robot do if localization is lost during a mapping mission?` (`lost-localization-mapping`)
- `What should the robot do if localization is lost while docking?` (`lost-localization-docking`)
- `What should the robot do if localization is lost during teleoperation?` (`lost-localization-remote-control`)
- `What should the robot do if localization is lost during a laboratory bench test?` (`lost-localization-test-bench`)

## New knowledge exercise

1. Ask `What is a tactile sensor array?` (expected unknown on a clean seed).
2. Teach `Tactile sensor array` with a definition and alias `tactile matrix`.
3. Repeat the first question and ask `Explain the tactile matrix.`
4. Check the native memory explorer before treating it as a confirmed new fact.
