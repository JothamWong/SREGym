import xml.etree.ElementTree as ET


def parse_sliver_info(xml_text):
    root = ET.fromstring(xml_text)

    # Get experiment description
    rspec_tour = root.find(
        ".//{http://www.protogeni.net/resources/rspec/ext/apt-tour/1}description"
    )
    description = rspec_tour.text if rspec_tour is not None else "No description"

    # Get expiration
    expiration = root.get("expires", "No expiration date")

    # Parse node information
    nodes = []
    for node in root.findall(".//{http://www.geni.net/resources/rspec/3}node"):
        node_info = {
            "client_id": node.get("client_id"),
            "component_id": node.get("component_id"),
            "hardware": node.find(
                ".//{http://www.protogeni.net/resources/rspec/ext/emulab/1}vnode"
            ).get("hardware_type"),
            "os_image": node.find(
                ".//{http://www.protogeni.net/resources/rspec/ext/emulab/1}vnode"
            ).get("disk_image"),
        }

        # Get host information
        host = node.find(".//{http://www.geni.net/resources/rspec/3}host")
        if host is not None:
            node_info["hostname"] = host.get("name")
            node_info["public_ip"] = host.get("ipv4")

        # Get interface information
        interface = node.find(".//{http://www.geni.net/resources/rspec/3}interface")
        if interface is not None:
            ip = interface.find(".//{http://www.geni.net/resources/rspec/3}ip")
            if ip is not None:
                node_info["internal_ip"] = ip.get("address")
                node_info["netmask"] = ip.get("netmask")

        nodes.append(node_info)

    # Get location information
    location = root.find(
        ".//{http://www.protogeni.net/resources/rspec/ext/site-info/1}location"
    )
    location_info = {
        "country": location.get("country") if location is not None else None,
        "latitude": location.get("latitude") if location is not None else None,
        "longitude": location.get("longitude") if location is not None else None,
    }

    return {
        "description": description,
        "expiration": expiration,
        "nodes": nodes,
        "location": location_info,
    }
