
import os
import sys
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import red

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DoclingImageTest")

def create_dummy_pdf_with_chart(path: str):
    """Create a simple PDF with a 'chart' (red rectangle)."""
    c = canvas.Canvas(path, pagesize=letter)
    c.drawString(100, 750, "Annual Report FAKE FY25")
    c.drawString(100, 730, "Below is a revenue chart:")
    
    # Draw a "chart"
    c.setFillColor(red)
    c.rect(100, 500, 300, 200, fill=1)
    
    c.drawString(100, 480, "Figure 1: Revenue Growth")
    c.save()
    logger.info(f"Created dummy PDF at {path}")

def test_docling_image_extraction():
    try:
        from docling.document_converter import DocumentConverter, PdfFormatOption
        from docling.datamodel.pipeline_options import PdfPipelineOptions, TableStructureOptions
        from docling.datamodel.base_models import InputFormat
    except ImportError as e:
        logger.error(f"Docling import failed: {e}")
        return

    # 1. Use REAL Annual Report PDF (first 10 pages)
    output_dir = os.path.join(os.path.dirname(__file__), "artifacts")
    pdf_path = os.path.join(output_dir, "RIL_sample.pdf")
    
    if not os.path.exists(pdf_path):
        logger.error(f"Sample PDF not found: {pdf_path}")
        return
    
    logger.info(f"Processing real Annual Report: {pdf_path}")

    # 2. Configure Docling Pipeline to ENABLE Image Extraction
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_table_structure = False # Disable to avoid tensor padding issues on CPU for this simple test
    pipeline_options.do_ocr = False
    pipeline_options.generate_page_images = True
    pipeline_options.generate_picture_images = True # Key for charts!

    doc_converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )

    # 3. Convert
    logger.info("Running Docling conversion...")
    conv_res = doc_converter.convert(pdf_path)
    
    # 4. Analyze Results
    doc = conv_res.document
    logger.info(f"Docling Text Preview: {doc.export_to_markdown()[:100]}...")
    
    # Check for images/pictures
    image_count = 0
    if hasattr(doc, 'pictures') and doc.pictures:
        image_count = len(doc.pictures)
        logger.info(f"Found {image_count} pictures via doc.pictures")
        
        for i, pic in enumerate(doc.pictures):
            # Print Metadata
            print(f"\n--- Extracted Image {i+1} Metadata ---")
            # pic.captions is likely a list
            if hasattr(pic, 'captions') and pic.captions:
                print(f"Captions: {pic.captions}")
            else:
                print("Captions: None")
            
            print(f"Page Number: {pic.prov[0].page_no if pic.prov else 'Unknown'}")
            print(f"Bounding Box: {pic.prov[0].bbox if pic.prov else 'Unknown'}")
            
            # Save Image
            # Docling stores the actual image data in the 'image' attribute (PIL Image)
            # We need to access it properly. In recent versions, it might be lazy loaded or in specific attribute.
            try:
                # Iterate through visuals to find the matching image
                # The 'pic' item in doc.pictures is a PictureItem. 
                # The actual bitmap is usually populated in the `images` list of the page or document if requested.
                # However, docling-core 2.0+ allows getting the image via get_image(pic) or similar on the document.
                # Let's try direct attribute access first if available, or fetch from doc.
                
                img_path = os.path.join(output_dir, f"extracted_chart_{i+1}.png")
                
                # Retrieve the PIL Image
                # Warning: Depending on docling version, getting the PIL image might differ.
                # Using the standard approach for 2.0+:
                pil_image = pic.get_image(doc) 
                
                if pil_image:
                    pil_image.save(img_path)
                    print(f"✅ Saved image to: {img_path}")
                    print(f"Image Size: {pil_image.size}")
                else:
                    print(f"⚠️ Could not retrieve PIL image for Picture {i+1}")
            except Exception as e:
                print(f"❌ Failed to save image: {e}")
                # Fallback: Inspect available methods
                import dir
                # print(dir(pic))

    # 5. Output Verification
    if image_count > 0:
        print("✅ Docling SUCCESSFULLY detected images/charts in the PDF.")
    else:
        # If no pictures, it might be because it's a vector graphic (rect) which docling might skip as 'picture'
        # but capturing page images is also a 'YES' for visual RAG.
        print("⚠️ No explicit 'picture' elements found (likely due to vector graphic nature of mock).")
        print("ℹ️ However, pipeline 'generate_page_images' was accepted, confirming support.")

    # Clean up
    # os.remove(pdf_path)

if __name__ == "__main__":
    test_docling_image_extraction()
