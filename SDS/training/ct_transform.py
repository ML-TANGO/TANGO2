from monai.transforms.compose import Compose, OneOf
from monai.transforms.utility.array import EnsureType, Lambda
from monai.transforms.croppad.array import RandSpatialCrop, CenterSpatialCrop
from monai.transforms.spatial.array import RandAffine, Resize
from monai.transforms.intensity.array import RandShiftIntensity, RandGaussianNoise

TARGET_SIZE = (224, 224, 160)             # (D, H, W)

def _clamp(img):                          # keep dynamic range safe
    return img.clamp_(0.0, 1.0)

# ---------------- TRAIN -------------------------------------------------------
def get_train_transform():
    return Compose([
        EnsureType(),
        
        # Either resize OR random crop (50/50 chance)
        OneOf([
            Resize(spatial_size=TARGET_SIZE, mode="trilinear"),
            RandSpatialCrop(roi_size=TARGET_SIZE, random_size=False),
        ]),

        # only very mild affine, no flips!
        RandAffine(
            prob=0.3,
            rotate_range=(0.0, 0.0, 3.1416/36),   # ±5° around axial axis
            scale_range=(0.05, 0.05, 0.05),       # ±5 % iso
            mode="nearest"
        ),

        RandShiftIntensity(offsets=0.08, prob=0.3),
        RandGaussianNoise(prob=0.25, mean=0.0, std=0.015),
        Lambda(_clamp),
    ])

# ---------------- VAL / TEST --------------------------------------------------
def get_val_transform():
    return Compose([
        EnsureType(),
        Resize(spatial_size=TARGET_SIZE, mode="trilinear"),  # Always resize for validation
        Lambda(_clamp),
    ])