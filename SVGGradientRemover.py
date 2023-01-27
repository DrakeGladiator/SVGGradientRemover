import xml.etree.ElementTree as ET
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# Remove gradients from svg file and replace them by solid color
tree = ET.parse("Graphs-Screenshot.svg")
root = tree.getroot()
print("SVG parsed!")
for descendant in root.findall("{*}defs/{*}linearGradient"):
    print(descendant)
    id = descendant.get("id")
    print("id: " + id)

    # Might be extended to extract average of multiple colors
    color = descendant[0].get("stop-color")
    print("color: " + color)
    print("{*}g/{*}"+id)

    # Replace all gradients with solid color
    for gradient in root.iterfind("{*}g/"):
        if gradient.get("fill") == ("url(#"+id+")"):
            print("old gradient:", gradient.get("fill"))
            gradient.set("fill", color)
            print("new gradient:", gradient.get("fill"))
tree.write("newSVG.svg", encoding="UTF-8")

# Save as PDF
rlg = svg2rlg("newSVG.svg")
renderPDF.drawToFile(rlg, "Graphs-Screenshot.pdf")