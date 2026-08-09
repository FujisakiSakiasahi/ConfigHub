# ConfigHub User Guide

ConfigHub is a web app for designing Time-Sensitive Networking (TSN) topologies
and automatically generating a Gate Control List (GCL) schedule for them using
a trained GraphSAGE GNN model, instead of hand-computing switch/talker gate
timing.

Given a network topology (talkers, switches, listeners, links) and the traffic
streams each talker sends, ConfigHub predicts the GCL — the sequence of
gate-open windows on each scheduled port — validates it, and exports it as XML
ready to load onto TSN-capable devices.

## Pages

- **Dashboard** — overview of network configuration status. (Coming soon.)
- **Topology Manager** — build a network topology (talkers/switches/listeners
  and the links between them) and define the traffic workload — the streams
  each talker sends, with type, priority (PCP), gate, period, and packet size.
  See [`topology_view.py`](../../views/topology_manager/topology_view.py).
- **Configuration Generation** — pick a trained model, check readiness of the
  topology/workload inputs, run inference to generate the GCL schedule,
  validate it, and export it to XML. See
  [`config_view.py`](../../views/configuration_generation/config_view.py).
- **Logs** — audit trail and system event history. (Coming soon.)
- **Documentation** — this section: user guides and technical reference,
  listed in the panel on the left (driven by [`index.md`](../index.md)).

## Typical workflow

1. Open **Topology Manager** and define the topology: number of talkers,
   switches, and listeners, the link datarate, and the edges connecting them.
2. In the same page, define each talker's workload: add streams with a type
   (`TT7`/`TT6`/`TT5` scheduled, or `BE`/`AVB` best-effort), PCP, gate, period,
   and packet size.
3. Go to **Configuration Generation**, select a trained model, and confirm the
   readiness checklist is green (topology loaded, at least one stream
   defined, model available).
4. Click **Generate GCL** to run inference. The predicted schedule is
   validated automatically (durations should sum to within 5% of the
   topology's cycle time — see
   [`data_json.md`](data_json.md#3-gcl-output--training-label)).
5. Export the validated schedule as XML for deployment.

## Related reference

- [`data_json.md`](data_json.md) — the JSON schema for topology, workload,
  gcl, and performance data used throughout the app.
- [`model_training.md`](model_training.md) — how to train a new GraphSAGE
  model checkpoint if you need to update or retrain the one used for
  inference.
