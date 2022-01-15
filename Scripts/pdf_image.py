import sys, fitz  # import the bindings
# file path you want to extract images from
fname = "239483.pdf"
#fname = sys.argv[1]  # get filename from command line
doc = fitz.open(fname)  # open document
for page in doc:  # iterate through the pages
    pix = page.get_pixmap()  # render page to an image
    svg = page.get_svg_image(matrix=fitz.Identity)
    with open('output.svg', 'a') as f:
        f.write(svg)
    pix.save("page-%i.png" % page.number)  # store image as a PNG