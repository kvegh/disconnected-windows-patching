"""Read-only libvirt topology inspection for the evaluation activation playbook."""

import json
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
        result.append({
            "mac": mac.get("address", "").lower() if mac is not None else "",
            "type": interface.get("type"),
            "source": dict(source.attrib) if source is not None else {},
            "model": model.get("type") if model is not None else None,
            "link": link.get("state", "up") if link is not None else "up",
        })
    return sorted(result, key=lambda item: item["mac"])


def inspect(domain, run=subprocess.check_output):
    def virsh(*args):
        return run(["virsh", "--connect", "qemu:///system", *args], text=True)

    live_xml = virsh("dumpxml", domain)
    persistent_xml = virsh("dumpxml", domain, "--inactive")
    root = ET.fromstring(persistent_xml)
    return {
        "name": root.findtext("name"),
        "uuid": root.findtext("uuid"),
        "marker": root.findtext("description"),
        "running": domain in virsh("list", "--name").splitlines(),
        "live": interfaces(live_xml),
        "persistent": interfaces(persistent_xml),
    }


if __name__ == "__main__":
    print(json.dumps(inspect(sys.argv[1]), sort_keys=True))
