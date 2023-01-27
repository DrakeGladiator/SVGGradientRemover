# SVGGradientRemover
Small script to replace "fake" gradients generated by QSvgGenerator() in PySide6, to become compatible with svglib to export svg as pdf by using svg2rlg() and renderPDF.drawToFile()

It successfully searches for linear gradients within a svg file and extracts a solid color that is then used to replace the corresponding gradient fill.
At the moment it only looks for linear gradients and does just take the first color as template. The script could be extendend by other gradient types and a method that extracts multiple colors to build an average color as template.
