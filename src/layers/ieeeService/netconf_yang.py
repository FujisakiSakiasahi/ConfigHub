"""GCL -> NETCONF/YANG XML conversion, per the ieee802-dot1dc-sched-if YANG model."""

import xml.etree.ElementTree as ET


def gcl_to_xml(run: dict, gcl: list) -> str:
    """Render the GCL as IEEE 802.1Q-Sched gate-parameter-table XML,
    matching the ieee802-dot1dc-sched-if YANG model."""
    cycle_ns = run["topology"]["gcl_cycle_time_ns"]

    root = ET.Element("interfaces", xmlns="urn:ietf:params:xml:ns:yang:ietf-interfaces")
    for entry in gcl:
        iface = ET.SubElement(root, "interface")
        ET.SubElement(iface, "name").text = entry["parent_id"]
        gpt = ET.SubElement(
            iface, "gate-parameter-table",
            xmlns="urn:ieee:std:802.1Q:yang:ieee802-dot1dc-sched-if",
        )
        ET.SubElement(gpt, "gate-enabled").text = "true"
        acl = ET.SubElement(gpt, "admin-control-list")
        for seq in entry["gcl_sequences"]:
            gce = ET.SubElement(acl, "gate-control-entry")
            ET.SubElement(gce, "index").text = str(seq["sequence_index"])
            ET.SubElement(gce, "operation-name").text = "sched:set-gate-states"
            ET.SubElement(gce, "gate-states-value").text = str(int(seq["gate_bitmask"], 2))
            ET.SubElement(gce, "time-interval-value").text = str(seq["duration_ns"])
        act = ET.SubElement(gpt, "admin-cycle-time")
        ET.SubElement(act, "numerator").text = str(cycle_ns)
        ET.SubElement(act, "denominator").text = "1000000000"

    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="unicode")


def validate_xml(xml_str: str) -> list[dict]:
    checks = []
    try:
        ET.fromstring(xml_str)
        checks.append({"name": "XML well-formed", "passed": True, "detail": "Parsed back successfully"})
    except ET.ParseError as e:
        checks.append({"name": "XML well-formed", "passed": False, "detail": str(e)})
    return checks
