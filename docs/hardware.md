# Hardware Design: Scanning Chamber

## Overview
A controlled physical environment is necessary to get consistent images for the vision models. The chamber blocks external light and provides uniform internal illumination.

## Specifications
- **Dimensions**: 30cm x 20cm x 25cm (L x W x H) dark enclosure
- **LED**: High-brightness warm white LED (3W-5W) with an acrylic diffuser, mounted on top for transillumination (candling)
- **Camera**: Bottom or side mount, positioned 15-20cm from the egg
- **Egg Holder**: Silicone cup or custom 3D-printed cradle, centered
- **Sensors**: DHT22 for temperature and humidity, optional BH1750 for ambient light

## Wiring
```
Pi GPIO <--> DHT22
Pi USB  <--> Camera
Power   <--> LED
```

## Assembly Steps
1. Prepare the 30x20x25cm enclosure.
2. Paint the interior matte black to reduce reflections.
3. Mount the LED and diffuser at the top center.
4. Mount the egg holder in the center of the base.
5. Mount the camera focusing on the egg holder.
6. Install the DHT22 sensor inside the chamber.
7. Route wiring to the external controller (Raspberry Pi).
8. Connect power and test lighting.

## Safety Notes
Use low voltage components. Ensure adequate ventilation if the LED runs hot.

## Future Improvements
Motorized rotation of the egg, conveyor belt for batch processing.
