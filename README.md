# Carson's EasyLabel Extractor
A simple tool to extract and save just the 4x6 shipping label from PDF files such as amazon return labels for those who have a thermal or other shipping label printers. Select a region, preview it, and it will automatically convert your capture as a high-quality pre-formatted PDF for your label printer. The program enables users to visually select regions of interest (ROIs) from PDF pages and save these selections as high-resolution 4x6 PDF labels. This project is built with Python and leverages key libraries such as tkinter for the graphical user interface, pdf2image for PDF conversion, and cv2 for image processing.

# Demo:

**Step 1:** 
Open the program and click the "Select PDF File" button.

![image](https://github.com/user-attachments/assets/da38bec7-22c2-43f1-922a-31e97b1c980f)

**Step 2:** 
You will see a new window appear with the PDF you selected, click and hold on one end of the label and drag to the corner opposite and accross from your first selection and release to highlight the entire shipping label on the pdf.

![image](https://github.com/user-attachments/assets/2811fa26-f389-447a-84a5-43f1d963cd49)

**Step 3:** 
Hit enter when you selected the label from the PDF. You will see the automatically formatted shipping label preview in the program now, if you are satisfied, you repeat the steps above from this screen. If you're satisfied, press the "Save Label" button on the bottom right. This will prompt you where to save the new label, and once saved it will automattically opened the saved file with your default .pdf file extension program.

![image](https://github.com/user-attachments/assets/41321c3f-203e-4b20-b137-023c6b0290f5)

**Step 4:** 
In the PDF preview page, select the print button at the top.

![image](https://github.com/user-attachments/assets/e6e01f4d-4996-4a75-8d7b-be2dce9b57d3)

**Step 5:** 
To send the label to your shipping label printer, please ensure you've made all the necessary selections in the highlighted regions shown below. Paper size for a 4x6 Label printer should be set to 100mm*150mm or just 4x6 inches if that option is there but they are the same thing. Once that is done, click on the print button on the bottom of the page! This will send your label to your printer of choice and you will have yourself a perfectly formatted shipping label from your PDF.

![image](https://github.com/user-attachments/assets/8876b8a3-f0ea-4fe5-992f-f83289470256)

**Final product:**

![IMG_5676 (1)](https://github.com/user-attachments/assets/0a2eca4a-933d-4b8e-ab12-ada6997f30b0)

# Key Features: 
1. PDF Selection and Conversion: Users can load PDF files and extract their first page as a high-resolution image.
2. Region of Interest Selection: An interactive interface allows users to select areas from the image with adjustable scaling to match the screen size.
3. Preview Functionality: The selected region is displayed within the application for verification.
4. Label Saving: The selected area can be resized to fit a standard 4x6 label size and saved as a PDF.
5. Clear and Reset Options: Users can easily clear the selection and choose a different PDF file.
6. Streamlined UI: The application features a clean, accessible design with hover effects and button state management.

This tool is ideal for quickly generating labels from existing PDF documents, whether for organizational purposes, shipping, or archiving needs. I personally created this project to get just the shipping labels from amazon return pdfs to print directly with my thermal printer!
