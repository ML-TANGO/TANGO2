# Report Generation Evaluation Docker

This Docker setup provides build, test, and export scripts for the container.

## Build

Build the Docker image with the provided script:

```bash
./build.sh
```

Ensure the script is executable:

```bash
chmod +x build.sh
```


## Testing

To verify functionality, run:

```bash
./test.sh
```

Ensure the script is executable:

```bash
chmod +x test.sh
```

### Test inputs

Place your test images in the `./test` directory. Supported image formats:

* `.nii.gz`
* `.mha`

After running, output results will be saved under `ctchat-output-volume-suffix`.

## Exporting

Use the `export.sh` script to export the Docker container and package the results:

```bash
./export.sh
```

