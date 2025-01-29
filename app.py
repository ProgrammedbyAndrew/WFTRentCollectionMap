#!/usr/bin/env python3

import os
import json
from flask import Flask, render_template_string
from occupant_service import get_leases_data

app = Flask(__name__)

# Keep your custom Jinja delimiters
app.jinja_options = {
    'block_start_string': '(%',
    'block_end_string': '%)',
    'variable_start_string': '((',
    'variable_end_string': '))',
    'comment_start_string': '(#',
    'comment_end_string': '#)'
}

def occupantColor(occupant_list):
    """
    Only two states:
      - If sum of balances > 0 => #ff8a8a (red, Past Due)
      - Otherwise => #8ae89f (green, On Time)
    """
    total_bal = sum(o["balance"] for o in occupant_list)
    if total_bal > 0:
        return "#ff8a8a"  # red
    return "#8ae89f"      # green

@app.route("/")
def index():
    # 1) occupant data
    all_data = get_leases_data()
    # 2) Filter for the property "World Food Trucks"
    filtered = [r for r in all_data if r["property_name"] == "World Food Trucks"]

    # 3) load map_layout.json
    try:
        with open("map_layout.json", "r") as f:
            map_data = json.load(f)
    except:
        map_data = None

    if not map_data:
        map_data = {"planeWidth": 600, "planeHeight": 800, "booths": []}
    planeW = map_data.get("planeWidth", 600)
    planeH = map_data.get("planeHeight", 800)
    booths = map_data.get("booths", [])

    # occupant_map => { label.upper(): [ occupantData, ... ] }
    occupant_map = {}
    for row in filtered:
        occupant_name = row["occupant_name"]
        loc_str       = (row["location"] or "").strip()
        bal           = row["balance"]
        lease_id      = row["lease_id"]
        end_date      = row["lease_end_date"]

        if loc_str and loc_str != "N/A":
            for t in loc_str.split():
                key = t.upper().strip()
                occupant_map.setdefault(key, []).append({
                    "occupant_name": occupant_name,
                    "lease_id": lease_id,
                    "lease_end": end_date,
                    "balance": bal,
                    "location": loc_str
                })

    # color-code each booth
    for b in booths:
        label_up = b.get("label", "").upper().strip()
        occupant_list = occupant_map.get(label_up, [])
        if occupant_list:
            b["occupants"] = occupant_list
            b["color"]     = occupantColor(occupant_list)
        else:
            b["occupants"] = []
            b["color"]     = "#bdbdbd"  # vacant / gray

    # The HTML only has two legend items: Past Due (red), On Time (green)
    html_template = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>World Food Trucks - Rent Collection Map</title>
  <style>
    body {
      font-family: sans-serif;
      margin: 0; padding: 0;
    }
    h1 { text-align: center; margin: 20px 0 10px; }
    .pageContent { padding-bottom: 90px; margin: 0 20px; }
    .legend {
      position: fixed; bottom: 0; left: 0; width: 100%;
      background: #fff; border-top: 2px solid #333;
      padding: 8px; z-index: 999; display: flex;
      justify-content: center; gap: 40px; /* space out the items */
      flex-wrap: wrap;
    }
    .legend-item {
      display: flex; align-items: center; margin: 4px 8px;
      cursor: pointer; /* we will click for a small explanation */
    }
    .color-box {
      width: 20px; height: 20px; margin-right: 6px; border: 2px solid #333;
    }
    #mapContainer {
      display: block; margin: 0 auto; max-width: 100%; position: relative; background: #fff;
    }
    .booth {
      position: absolute; box-sizing: border-box; border: 2px solid #111;
      display: flex; justify-content: center; align-items: center;
      font-weight: bold; font-size: 12px; color: #000; cursor: pointer;
    }
  </style>
</head>
<body>
  <h1>World Food Trucks - Rent Collection Map</h1>

  (% if booths|length > 0 %)
    <div class="pageContent">
      <div id="mapContainer" style="width:__PW__px; height:__PH__px;"></div>
    </div>

    <div class="legend">
      <div class="legend-item" onclick="alert('Green means occupant is ON TIME (Balance = $0).')">
        <div class="color-box" style="background:#8ae89f;"></div>
        <span>On Time</span>
      </div>
      <div class="legend-item" onclick="alert('Red means occupant is PAST DUE (Balance > $0).')">
        <div class="color-box" style="background:#ff8a8a;"></div>
        <span>Past Due</span>
      </div>
    </div>

    <script>
    function initMap() {
      let planeWidth  = __PW__;
      let planeHeight = __PH__;
      const ctn = document.getElementById("mapContainer");

      ctn.style.width  = planeWidth + "px";
      ctn.style.height = planeHeight + "px";

      const data = __BOOTH_JSON__;

      data.forEach(b => {
        const div = document.createElement("div");
        div.className = "booth";
        div.style.left   = b.x + "px";
        div.style.top    = b.y + "px";
        div.style.width  = b.width + "px";
        div.style.height = b.height + "px";

        div.textContent = b.label;
        div.style.backgroundColor = b.color || "#bdbdbd"; 

        let occList = b.occupants || [];
        if (occList.length > 0) {
          // Figure out if this occupant is On Time or Past Due
          let colorMeaning = (b.color === "#ff8a8a") ? "PAST DUE" : "ON TIME ($0)";
          let info = occList.map(o => {
            return (
              "LeaseID: " + o.lease_id + "\\n" +
              "Occupant: " + o.occupant_name + "\\n" +
              "End: " + o.lease_end + "\\n" +
              "Balance: $" + o.balance.toFixed(2) + "\\n" +
              "Indicator: " + colorMeaning
            );
          }).join("\\n----\\n");
          div.onclick = () => {
            alert("Spot " + b.label + "\\n" + info);
          }
        } else {
          div.onclick = () => {
            alert("Spot " + b.label + "\\nVacant");
          }
        }

        ctn.appendChild(div);
      });

      // If browser window is narrower than planeWidth, scale the map
      let containerParent = ctn.parentNode;
      let actualWidth = containerParent.clientWidth;
      if (planeWidth > 0 && actualWidth < planeWidth) {
        let scale = actualWidth / planeWidth;
        ctn.style.transformOrigin = "top left";
        ctn.style.transform       = "scale(" + scale + ")";
      }
    }
    window.onload = initMap;
    </script>
  (% else %)
    <p style="margin:20px;">No map_layout.json or no booths found.</p>
  (% endif %)
</body>
</html>
    """

    from json import dumps
    booth_json_str = dumps(booths)

    rendered = render_template_string(html_template, booths=booths)
    rendered = rendered.replace("__PW__", str(planeW))
    rendered = rendered.replace("__PH__", str(planeH))
    rendered = rendered.replace("__BOOTH_JSON__", booth_json_str)

    return rendered

if __name__ == "__main__":
    app.run(debug=True, port=5001)