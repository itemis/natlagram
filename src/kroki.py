"""here lives code that interfaces with the kroki server's API"""

import base64
import zlib
import requests
from pathlib import Path

import matplotlib.image as mpimg
import matplotlib.pyplot as plt
import cairosvg
import pdfkit # NOTE: this dependency is not maintained
import weasyprint

import const
import data_io

plt.rcParams['savefig.dpi'] = 300

def check_kroki_server(server_url: str = const.SERVER_URL) -> None:
    """Check if the kroki server is running
    
    args:
        server_url: the URL of the kroki server    
    """
    full_url = f"http://{server_url}/health"
    try:
        response = requests.get(full_url)
        if response.status_code == 200:
            print(f"Kroki server is running at {full_url}")
    except requests.exceptions.ConnectionError as e:
        raise requests.exceptions.ConnectionError(f"Kroki server is not running at {full_url}. Please start it with 'docker compose up'.") from e
        

def generate_url_from_str(diagram: str, diagram_api: str, output_format: str, server_url: str = const.SERVER_URL) -> str:
    """Generate a URL from a string
    
    args:
        diagram: the diagram as a string
        diagram_api: the api chosen for the the diagram, e.g. "dot" means Graphviz
        output_format: the format of generated image, e.g. SVG, PNG, ...
    
    returns:
        the URL to the diagram
    """
    diagram = diagram.encode('utf-8')
    url_diagram = base64.urlsafe_b64encode(zlib.compress(diagram, 9)).decode('ascii')
    url = f"http://{server_url}/{diagram_api}/{output_format}/{url_diagram}"
    return url

def generate_url_from_file(path: str, diagram_api: str, output_format: str, server_url: str) -> str:
    """Generate a URL from a file
    
    args:
        path: the path to the file
        diagram_api: the api chosen for the the diagram, e.g. "dot" means Graphviz
        output_format: the format of generated image, e.g. SVG, PNG, ...
        server_url: the URL of the kroki server
    
    returns:
        the URL to the diagram
    """
    with open(path, 'rb') as f:
        diagram = f.read()
    url_diagram = base64.urlsafe_b64encode(zlib.compress(diagram, 9)).decode('ascii')
    url = f"http://{server_url}/{diagram_api}/{output_format}/{url_diagram}"
    return url

def save_image_from_url(url: str, output_path: str) -> None:
    """Generate an image from a URL
    
    args:
        url: the URL to the diagram
        output_path: the path to the output image
    """
    r = requests.get(url)
    if r.status_code != 200:
        reason = "Kroki returned non-200 status code\n"
        reason += r.text
        raise requests.RequestException(reason)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "wb") as f:
        f.write(r.content)

def convert_text_to_image(diagram: str, diagram_api: str, output_format: str, server_url: str) -> bytes:
    """Generate an image from a string
    
    args:
        diagram: the diagram as a string
        diagram_api: the api chosen for the the diagram, e.g. "dot" means Graphviz
        output_format: the format of generated image, e.g. SVG, PNG, ...
        server_url: the URL of the Kroki server
    
    returns:
        the image as a byte array
    """
    url = generate_url_from_str(diagram, diagram_api, output_format, server_url)
    r = requests.get(url)
    return r.content

def check_image_valid(url: str, service: str, code: str) -> bool:
    """Check if an image was generated successfully
    
    args:
        url: the URL to the diagram
        service: the service used to generate the image (Diagram API), e.g. "dot" means Graphviz
        code: the code describing the diagram, e.g. "graph LR; A-->B;"

    return:
        True if the image was generated successfully, False otherwise
    """
    def check_copy_services(response, code: str):
        """The D2 generated image shouldn't yield a copy of the code"""
        return False if code in response.text else True
    def check_ditaa(response):
        """Ditaa returns an 'This XML file does not appear to have any style information associated with it. The document tree is shown below.' if the code is invalid but response code is still 200"""
        return False if "This XML file does not appear to have any style information" in response.text else True
    def check_service_mermaid(response):
        """Mermaid returns an 'Syntax Error' if the code is invalid but response code is still 200"""
        return False if "Syntax error in graph" in response.text else True

    r = requests.get(url)
    if r.status_code == 200:
        if service in ["d2", "ditaa", "nomnoml"]:
            return check_copy_services(r, code)
        if service == "ditaa":
            return check_ditaa(r)
        elif service == "mermaid":
            return check_service_mermaid(r)
        return True
    else:
        return False

def convert_svg_to_png(svg: Path) -> Path:
    """Convert an SVG image to a PNG image
    NOTE:
        Doesn't work properly on Ubuntu hosts when Ubuntu can't display the SVG text
        Workaround is screenshot or print to pdf

    args:
        svg: the path to the SVG image

    returns:
        the path to the PNG image
    """
    cairosvg.svg2png(url=str(svg), write_to=str(svg.with_suffix(".png")), dpi=300)
    return svg.with_suffix(".png")

def print_image_from_url(url: str, output_path: str) -> None:
    """Generate an image from a URL and print it
    
    args:
        url: the URL to the diagram
        output_path: the path to the output image
    """
    r = requests.get(url)
    if r.status_code == 200:
        pdfkit.from_url(url, output_path)
    else:
        reason = "Kroki returned non-200 status code\n"
        reason += r.text
        raise requests.RequestException(reason)

def print_image_from_url_weasyprint(url: str, output_path: str) -> None:
    """Generate an image from a URL and print it
    
    args:
        url: the URL to the diagram
        output_path: the path to the output image
    """
    r = requests.get(url)
    if r.status_code == 200:
        weasyprint.HTML(url).write_pdf(output_path)
    else:
        reason = "Kroki returned non-200 status code\n"
        reason += r.text
        raise requests.RequestException(reason)

def show_image(path: Path) -> None:
    """Show an image
    
    args:
        path: the path to the image
    """
    with open(path, "rb") as f:
        img = mpimg.imread(f)
        plt.imshow(img)
        plt.show()

def test_failure_detection() -> bool:
    """Test that the failure detection works for each service

    Upon failure, each API responds differently, so we need to test each one to check whether a valid image was generated or not

    returns:
        True if all tests passed, False otherwise
    """
    diagrams = dict.fromkeys(const.SERVICES, "123 invalid 987")
    for service in const.SERVICES:
        code = diagrams[service]
        url = generate_url_from_str(code, service, "svg", const.SERVER_URL)
        if service == "svgbob": # don't know how to generate an invalid image for this service
            continue
        if check_image_valid(url, service, code):
            print(f"Failure detection failed for {service}")
            print(f"URL: {url}")
            return False
    return True

def save_images(img_url: str, work_dir: Path, file_name: str = "natlagram", show: bool = True) -> None:
    """save an image at a given url in multiple formats
    
    args:
        img_url: the url of the image
        work_dir: the directory to save the image in
        file_name: name given to image
        show: whether to show the image or not
    """
    svg = work_dir / f"{file_name}.svg"
    pdf = work_dir / f"{file_name}.pdf"
    svg = data_io.number_file_name(svg)
    pdf = data_io.number_file_name(pdf)
    save_image_from_url(img_url, svg)
    print_image_from_url(img_url, pdf)
    png = convert_svg_to_png(svg)
    if show:
        show_image(png)

if __name__ == "__main__":
    test_diagram = """
    blockdiag {
    A -> B;
    }
    """

    service = "blockdiag"
    img_url = generate_url_from_str(test_diagram, service, "svg", const.SERVER_URL)
    print(f"URL: {img_url}")
    parent = Path("temp")
    parent.mkdir(exist_ok=True)
    svg = Path("temp/test.svg")
    pdf = Path("temp/test.pdf")
    valid = check_image_valid(img_url, service, test_diagram)
    print(f"Valid: {valid}")
    save_image_from_url(img_url, svg)
    print_image_from_url(img_url, pdf)
    png = convert_svg_to_png(svg)
    show_image(png)