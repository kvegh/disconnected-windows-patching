# Purpose and language choice: [rationale](../docs/supporting-code.md#hypervisor-inspection-and-recovery).
"""Read-only libvirt topology inspection for the evaluation activation playbook."""

import ipaddress
import json
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


def interfaces(xml):
    root = ET.fromstring(xml)
    result = []
    for interface in root.findall("./devices/interface"):
        mac = interface.find("mac")
        source = interface.find("source")
        model = interface.find("model")
        link = interface.find("link")
        source_attributes = dict(source.attrib) if source is not None else {}
        if interface.get("type") == "network":
            # Live XML resolves a virtual network to its host bridge and
            # allocates a runtime port UUID. Neither belongs to inactive XML.
            # Keep network/portgroup and all unknown source attributes; a
            # bridge-type interface still needs its bridge source identity.
            source_attributes.pop("bridge", None)
            source_attributes.pop("portid", None)
        result.append({
            "mac": mac.get("address", "").lower() if mac is not None else "",
            "type": interface.get("type"),
            "source": source_attributes,
            "model": model.get("type") if model is not None else None,
            "link": link.get("state", "up") if link is not None else "up",
        })
    return sorted(result, key=lambda item: item["mac"])


def inspect(domain, run=subprocess.check_output, network=None):
    def virsh(*args):
        return run(["virsh", "--connect", "qemu:///system", *args], text=True)

    live_xml = virsh("dumpxml", domain)
    persistent_xml = virsh("dumpxml", domain, "--inactive")
    root = ET.fromstring(persistent_xml)
    result = {
        "name": root.findtext("name"),
        "uuid": root.findtext("uuid"),
        "marker": root.findtext("description"),
        "running": domain in virsh("list", "--name").splitlines(),
        "live": interfaces(live_xml),
        "persistent": interfaces(persistent_xml),
    }
    if network is not None:
        # Justification: [activation bounds](../docs/windows-evaluation-activation.md).
        net = ET.fromstring(virsh("net-dumpxml", network))
        ipv4 = [item for item in net.findall("ip") if item.get("family", "ipv4") == "ipv4"]
        if len(ipv4) != 1 or net.find("forward") is None:
            raise ValueError("Activation requires one IPv4 NAT network.")
        gateway = str(ipaddress.IPv4Address(ipv4[0].get("address")))
        references, macs = [], set()
        for name in virsh("list", "--all", "--name").splitlines():
            for args in [("dumpxml", name), ("dumpxml", name, "--inactive")]:
                items = interfaces(virsh(*args))
                macs.update(item["mac"] for item in items)
                if any(item["source"].get("network") == network for item in items):
                    references.append(name)
        result.update(
            hypervisor_machine_id=Path("/etc/machine-id").read_text().strip(),
            title=root.findtext("title"),
            disks=[item.get("file") for item in root.findall("./devices/disk/source")],
            all_macs=sorted(macs),
            activation_network={"name": network, "active": network in virsh("net-list", "--name").splitlines(),
                                "forward": net.find("forward").get("mode"),
                                "bridge": net.find("bridge").get("name"), "gateway": gateway,
                                "ipv6": net.get("ipv6") == "yes" or any(item.get("family") == "ipv6" for item in net.findall("ip")),
                                "domain_references": sorted(set(references))},
        )
    return result


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1], network=sys.argv[2] if len(sys.argv) > 2 else None), sort_keys=True))
