# EggVision AI — Optical Hardware Enclosure & Capture System Design
**Document Version:** 1.0.0  
**Classification:** Hardware Engineering, Optical Architecture & BOM Specification

---

## 1. System Overview & Optical Principles

Optical assessment of intact poultry eggs requires a strictly controlled physical environment to eliminate ambient illumination variations, eliminate specular reflections, and ensure reproducible geometric framing. 

The EggVision Scanning Chamber provides two distinct optical acquisition modes:
1. **Transillumination Candling Mode:** High-intensity diffused warm light transmits upwards through an aperture at the blunt pole of the egg, penetrating the shell to visualize the air cell silhouette and internal transmission characteristics against a dark background.
2. **Surface Reflectance Mode:** Even, diffuse visible illumination highlights external eggshell contours, texture, cracks, and surface pigmentation against a contrasting matte backdrop.

```
                           [ Light-Tight Enclosure Top ]
                                        │
                         [ Exhaust Vent / Light Trap ]
                                        │
           [ Camera Mount: Raspberry Pi Camera Mod 3 (Autofocus) ]
                   │ (150 mm Working Distance, 75° FoV)
                   ▼
        ┌─────────────────────────────────────────────────────────┐
        │                                                         │
        │                       Egg Subject                       │
        │                   (Oriented Blunt Up)                   │
        │                                                         │
        └───────────────────────────┬─────────────────────────────┘
                                    │
                    [ Soft Silicone Masking Ring ]
                                    │
                       [ Optical Diffuser Plate ]
                                    │
                  [ 5W High-CRI LED Illumination Source ]
                                    │
                     [ Aluminum Heat Sink & Chamber Base ]
```

---

## 2. Mechanical & Optical Specifications

### 2.1 Enclosure Construction
- **Internal Dimensions:** $300\,mm \text{ (Length)} \times 200\,mm \text{ (Width)} \times 250\,mm \text{ (Height)}$.
- **Material:** $5\,mm$ extruded matte black cast acrylic (PMMA) or 3D-printed PETG panels.
- **Interior Coating:** Coated with ultra-absorbent matte black coating (specular reflectance $< 1.5\%$ at $400–700\,nm$) to prevent parasitic light bouncing.
- **Light Trap Labyrinth:** Passive baffle vents at the base and top allow heat dissipation from high-power LEDs while blocking ambient room light (stray light rejection $> 99.8\%$).

### 2.2 Transillumination Aperture & Cradle
- **Pedestal:** Centered 3D-printed pedestal with a $25\,mm$ diameter circular aperture hole.
- **Gasket Mask:** Food-safe Shore A 30 silicone rubber gasket mounted around the rim of the aperture. When an egg is seated vertically (blunt pole down over the light or blunt pole up for candling), the silicone gasket forms an optical seal around the curvature of the shell, preventing bright stray light from spilling directly into the camera lens without passing through the egg.

### 2.3 Imaging Sensor & Optics
- **Primary Camera:** Raspberry Pi Camera Module 3 (Sony IMX708 sensor).
  - Sensor Resolution: $4608 \times 2592$ pixels ($11.9\,\text{Megapixels}$).
  - Optical Format: $1/2.43"$ ($7.4\,mm$ diagonal).
  - Pixel Pitch: $1.4\,\mu\text{m} \times 1.4\,\mu\text{m}$.
  - Lens: Fast $f/1.8$ aperture, $4.74\,mm$ focal length, motorized autofocus ($10\,cm$ to infinity).
  - Field of View (FoV): $75^\circ$ horizontal.
  - Optical Working Distance: Fixed at $160\,mm \pm 5\,mm$ above the egg center, yielding an optical resolution of approximately $35\,\text{pixels/mm}$.

### 2.4 Illumination Engineering
- **LED Emitter:** Bridgelux Vero 10 or Cree XP-E2 Warm White ($3000\text{K}$, $\text{CRI} \ge 90$).
  - Power: $3\text{W}–5\text{W}$, driven by a constant-current LED driver ($350\text{mA}–700\text{mA}$) with PWM dimming control.
  - Wavelength Peak: Warm spectral distribution ($580–630\,nm$) exhibits superior transmission through the calcium carbonate shell matrix compared to blue wavelengths ($400–480\,nm$).
- **Diffusion:** $2\,mm$ thick optical-grade sandblasted acrylic or frosted glass diffusion filter positioned $10\,mm$ beneath the silicone gasket to ensure Lambertian uniform illumination.
- **Thermal Management:** $40 \times 40 \times 20\,mm$ anodized aluminum pin-fin heatsink mounted directly to the thermal pad of the LED to maintain emitter junction temperature $< 65^\circ\text{C}$.

---

## 3. Electrical Architecture & Wiring Block Diagram

```
[ AC Mains 100-240V ] ──► [ 12V 3A DC Power Supply ] 
                                 │
     ┌───────────────────────────┴───────────────────────────┐
     ▼                                                       ▼
[ 5V 3A Buck Converter ]                        [ Constant Current LED Driver ]
     │                                                       │
     ▼                                                       ▼
[ Raspberry Pi 4B / Zero 2W ] ──(PWM GPIO 18)──► [ PWM Dimming Gate ] ──► [ High-CRI LED ]
     │
     ├───(CSI Ribbon Cable)────────────────────► [ Sony IMX708 Camera Module 3 ]
     │
     ├───(I2C / GPIO 4)────────────────────────► [ Sensirion SHT31-D Temp/Humidity Sensor ]
     │
     └───(Ethernet / Wi-Fi)────────────────────► [ EggVision Backend REST API (/api/v1/scan) ]
```

---

## 4. Bill of Materials (BOM) & Cost Analysis

The following hardware specification utilizes commercial off-the-shelf (COTS) parts and standard fabrication techniques:

| Item # | Component Description | Manufacturer / Part # | Qty | Unit Price (USD) | Source / Vendor |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **1** | Single-Board Computer (2GB RAM) | Raspberry Pi 4 Model B | 1 | $35.00 | Authorized Pi Reseller |
| **2** | Autofocus 12MP Camera Module | Raspberry Pi Camera Module 3 | 1 | $25.00 | Authorized Pi Reseller |
| **3** | High-CRI Warm White LED Emitter | Cree XP-E2 or Bridgelux Vero 10 | 1 | $4.50 | DigiKey / Mouser |
| **4** | Constant Current Buck LED Driver | Mean Well LDD-700L (700mA PWM) | 1 | $5.20 | DigiKey / Mouser |
| **5** | I2C Temperature & Humidity Sensor | Sensirion SHT31-D Breakout | 1 | $6.50 | Adafruit / SparkFun |
| **6** | Aluminum Pin-Fin Heatsink | $40 \times 40 \times 20\,mm$ Anodized | 1 | $3.20 | Electronics Supply |
| **7** | Optical Acrylic Diffuser Plate | $50 \times 50 \times 2\,mm$ Frosted PMMA | 1 | $2.50 | Optical Supply |
| **8** | Chamber Enclosure Panels (Cut) | $5\,mm$ Matte Black Cast Acrylic Sheet | 1 set | $18.00 | Local Laser Cutting / Ponoko |
| **9** | 3D-Printed Cradle & Silicone Gasket | PETG + Molded Silicone Ring | 1 set | $4.50 | In-house 3D Print / FDM |
| **10**| 12V 3A DC Power Supply & DC Jack | CUI Inc. / Mean Well GST36 | 1 | $12.00 | Electronics Supply |
| **11**| Hardware Fasteners, Standoffs, Wire | M3 Stainless Machine Screws & Standoffs | 1 lot | $5.00 | McMaster-Carr / Hardware Store|
| **TOTAL**| **Complete Scanning Enclosure** | **EggVision Hardware Kit v1.0** | | **$121.40** | **Academic / Commercial Prototype** |

---

## 5. Assembly Guidance & Calibration Protocol

### 5.1 Mechanical Assembly Steps
1. Assemble the 5 outer enclosure panels using interlocking acrylic joints and solvent bonding (acrylic cement) or M3 corner brackets.
2. Coat all internal seams with opaque silicone caulk to ensure 100% light impermeability.
3. Affix the aluminum heatsink to the chamber floor, mount the LED emitter using thermal adhesive, and position the diffuser $10\,mm$ above the emitter.
4. Mount the 3D-printed pedestal and silicone sealing ring centrally over the diffuser plate.
5. Install the camera module on the upper mounting plate, verifying that the optical axis passes perpendicular through the center of the egg cradle.
6. Install the SHT31-D sensor inside the chamber away from direct heatsink thermal dissipation.

### 5.2 Geometric & Optical Calibration Protocol
1. **Spatial Scale Calibration:** Place a calibrated $20 \times 20\,mm$ checkerboard optical target ($2\,mm$ square pitch) in the egg cradle. Execute spatial calibration to determine optical scaling:
   $$\text{Scale Ratio } (\text{pixels/mm}) = \frac{\text{Measured Feature Pixels}}{\text{Known Feature Millimeters}}$$
   Verify horizontal and vertical aspect ratios are within $1.00 \pm 0.01$.
2. **Exposure & White Balance Lock:** With the chamber sealed and transillumination active on an empty white reference target, set camera white balance gains ($R_{\text{gain}}, B_{\text{gain}}$) and fix sensor analog gain and shutter time. Lock automatic exposure to prevent fluctuating intensity histograms.
3. **Empty Frame Background Baseline:** Capture 10 frames with no egg present. Verify that all peripheral border pixels exhibit $L^* < 10$ in CIELAB space, verifying zero stray ambient light leakage.
