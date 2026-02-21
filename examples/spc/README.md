SPC outlook example GeoJSON files

This folder contains example SPC convective and fire-weather outlook GeoJSONs downloaded from `spc.noaa.gov` for development and testing.

Files are listed in `spc_files.txt`.

Note: these example files are large. They are present in your working copy but are not automatically committed to the repository by the helper script. If you want them added to Git, run:

```bash
git add examples/spc/*
git commit -m "examples(spc): add SPC outlook GeoJSON samples"
git push origin main
```

If you prefer not to commit raw GeoJSON into the repo, keep them locally and the manifest (`spc_files.txt`) will list what was downloaded.
