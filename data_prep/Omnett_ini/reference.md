File naming scheme:
omnetpp_[num_talkers/num_switch/num_listener]_[stream_profile_for_each_talker]

Stream profiles:
| ID | Stream |
|---|---|
| 1 |P7, P0|
| 2 |P7, P6|
| 3 |P7, P5|
| 4 |P6, P0|
| 5 |P5, P0|
| 6 |P6, P5|
| 7 |P7, P6, P0|
| 8 |P7, P5, P0|
| 9 |P7, P6, P5|
| A |P6, P5, P0|
| B |P7, P0, P0|
| C |P7, P7, P0|

Other than P0, P7, P6, P5 will go through the combination of interval ( 250us, 100us, 50us, 30us, 15us) and packet size (1000B, 500B, 256B, 100B, 64B) which is 25 combinations