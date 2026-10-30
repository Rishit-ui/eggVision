# EggVision AI — Operator & Researcher User Guide
**Document Version:** 1.0.0  
**Target Audience:** Laboratory Technicians, Quality Control Operators, Avian Researchers  
**Application URL:** `https://egg-vision.vercel.app`

---

## 1. Introduction to EggVision AI

EggVision AI is an interactive research and optical capture-screening platform for poultry egg evaluation. It allows operators to acquire controlled transillumination candling images, evaluate optical capture quality in real time, record environmental storage conditions, and build verified research datasets without fabricating unverified AI predictions.

---

## 2. Step-by-Step Operator Workflow

```
[ 1. Sign In ] ──► [ 2. Open Scan Console ] ──► [ 3. Position Egg & Capture ] ──► [ 4. Enter Metadata ] ──► [ 5. Review Capture Report ]
```

### Step 1: Authentication
1. Open `https://egg-vision.vercel.app` in any modern web browser (Chrome, Firefox, Safari, Edge).
2. Click **Sign In** in the navigation bar or visit `/login`.
3. Enter your authorized research email and password. Upon successful authentication, your JWT access session is established.

### Step 2: Accessing the Candling Capture Console
1. Navigate to **Scan** in the navigation bar (`/scan`).
2. Verify the system connection status indicator is green.

### Step 3: Specimen Positioning & Image Selection
1. Mount the egg in the EggVision scanning chamber:
   - For transillumination candling, place the egg vertically over the aperture with the blunt pole facing upward.
   - For surface imaging, ensure even diffuse lighting and an uncluttered matte background.
2. In the web interface, click the upload box to select an image file or drag and drop a capture directly (`.jpg`, `.png`, or `.webp`, up to $10\,\text{MB}$).
3. A client-side preview will display immediately. Verify that the full egg contour is centered within the frame.

### Step 4: Specimen & Environmental Metadata
In the right-hand panel, specify available capture parameters:
- **Egg Type:** White Shell, Brown Shell, Desi / Native, or Other.
- **Storage Condition:** Unknown, Refrigerated ($4^\circ\text{C}$), or Room Temperature ($20–25^\circ\text{C}$).
- **Ambient Temperature:** Chamber temperature in $^\circ\text{C}$ (e.g., `21.5`).
- **Relative Humidity:** Chamber humidity in $\%$ (e.g., `55.0`).

### Step 5: Processing the Scan
1. Click **Analyze Capture Quality**.
2. The browser submits the multipart scan to the backend API (`/api/v1/scan`).
3. If the capture passes optical screening, the application automatically redirects you to the detailed **Capture Report** (`/result/[id]`).

---

## 3. Understanding Capture Screening Warnings & Guidance

If the optical screening detects capture issues, a notification panel appears with specific actionable guidance:

| Warning Code | Explanation | Recommended Operator Action |
| :--- | :--- | :--- |
| `UNSUPPORTED_BACKGROUND` | The background is bright and uniform, preventing contour separation. | Place the egg inside the dark candling chamber or against a dark matte backdrop. |
| `NO_CANDIDATE_CONTOUR` | No isolated candidate shape was detected. | Reframe the egg centrally and verify that the subject is illuminated. |
| `MULTIPLE_CANDIDATES` | Multiple objects or eggs were found in the frame. | Ensure only one physical egg is inside the chamber during capture. |
| `BLUR_DETECTED` | The image is out of focus or suffered camera motion blur. | Refocus the lens and stabilize the camera mount before triggering capture. |
| `EXCESSIVE_CANDIDATE_GLARE`| Specular reflection exceeds $8\%$ of the candidate area. | Reposition the light source or install an optical diffuser plate. |
| `STRONG_CANDIDATE_SHADOWS` | Over $35\%$ of the candidate area is in deep shadow. | Add even fill lighting or increase transillumination power. |
| `CANDIDATE_PARTIALLY_VISIBLE_BORDER_CLIPPED` | The egg boundary touches the edge of the frame. | Move the camera further back or center the egg to ensure a visible margin. |

---

## 4. Transparent Capture Report (`/result/[id]`)

The report page clearly distinguishes verified physical observations from machine learning states:
- **Screened Candidate Geometry:** Displays measured pixel area, bounding width/height, aspect ratio, and orientation angle.
- **Normalized Artifact:** Shows the vertical affine-aligned, $512 \times 512$ CLAHE-enhanced image.
- **Model Status Notice:** Transparently declares: *"No trained model is currently loaded. Candidate geometry represents optical contour screening only."*
- **History & Batch Retrieval:** Scans are archived in **History** (`/history`) where they can be searched, filtered, and reviewed for longitudinal research.
