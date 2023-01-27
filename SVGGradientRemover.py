import xml.etree.ElementTree as ET
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPDF

# Remove gradients from svg file and replace them by solid color
# First open the svg file to be modified
tree = ET.parse("Graphs-Screenshot.svg")
root = tree.getroot()

# Search for the linearGradient tag within the svg file
for descendant in root.findall("{*}defs/{*}linearGradient"):
    print(descendant)
    id = descendant.get("id")
    print("id: " + id)

    # Extract the (first) color of the gradient as template
    # for solid color fill.
    # Might be extended to extract average of multiple colors
    color = descendant[0].get("stop-color")
    print("color: " + color)
    print("{*}g/{*}"+id)

    # Replace all gradients with previously extracted solid color
    for gradient in root.iterfind("{*}g/"):
        if gradient.get("fill") == ("url(#"+id+")"):
            print("old gradient:", gradient.get("fill"))
            gradient.set("fill", color)
            print("new solid color:", gradient.get("fill"))
            
# Save the edited svg file
tree.write("newSVG.svg", encoding="UTF-8")

# Convert svg to reportlab own rlg format
rlg = svg2rlg("newSVG.svg")
# Save a PDF out of rlg file
renderPDF.drawToFile(rlg, "Graphs-Screenshot.pdf")
