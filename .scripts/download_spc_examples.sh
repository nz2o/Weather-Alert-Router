#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p examples/spc
urls=(
 'day1otlk_cat_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson'
 'day1otlk_cat_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_cat.lyr.geojson'
 'day1otlk_torn_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_torn.nolyr.geojson'
 'day1otlk_torn_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_torn.lyr.geojson'
 'day1otlk_sigtorn_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sigtorn.nolyr.geojson'
 'day1otlk_sigtorn_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sigtorn.lyr.geojson'
 'day1otlk_hail_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_hail.nolyr.geojson'
 'day1otlk_hail_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_hail.lyr.geojson'
 'day1otlk_sighail_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sighail.nolyr.geojson'
 'day1otlk_sighail_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sighail.lyr.geojson'
 'day1otlk_wind_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_wind.nolyr.geojson'
 'day1otlk_wind_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_wind.lyr.geojson'
 'day1otlk_sigwind_nolyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sigwind.nolyr.geojson'
 'day1otlk_sigwind_lyr|https://www.spc.noaa.gov/products/outlook/day1otlk_sigwind.lyr.geojson'
 'day2otlk_cat_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_cat.nolyr.geojson'
 'day2otlk_cat_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_cat.lyr.geojson'
 'day2otlk_torn_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_torn.nolyr.geojson'
 'day2otlk_torn_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_torn.lyr.geojson'
 'day2otlk_sigtorn_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sigtorn.nolyr.geojson'
 'day2otlk_sigtorn_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sigtorn.lyr.geojson'
 'day2otlk_hail_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_hail.nolyr.geojson'
 'day2otlk_hail_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_hail.lyr.geojson'
 'day2otlk_sighail_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sighail.nolyr.geojson'
 'day2otlk_sighail_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sighail.lyr.geojson'
 'day2otlk_wind_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_wind.nolyr.geojson'
 'day2otlk_wind_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_wind.lyr.geojson'
 'day2otlk_sigwind_nolyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sigwind.nolyr.geojson'
 'day2otlk_sigwind_lyr|https://www.spc.noaa.gov/products/outlook/day2otlk_sigwind.lyr.geojson'
 'day3otlk_cat_nolyr|https://www.spc.noaa.gov/products/outlook/day3otlk_cat.nolyr.geojson'
 'day3otlk_cat_lyr|https://www.spc.noaa.gov/products/outlook/day3otlk_cat.lyr.geojson'
 'day3otlk_prob_nolyr|https://www.spc.noaa.gov/products/outlook/day3otlk_prob.nolyr.geojson'
 'day3otlk_prob_lyr|https://www.spc.noaa.gov/products/outlook/day3otlk_prob.lyr.geojson'
 'day3otlk_sigprob_nolyr|https://www.spc.noaa.gov/products/outlook/day3otlk_sigprob.nolyr.geojson'
 'day3otlk_sigprob_lyr|https://www.spc.noaa.gov/products/outlook/day3otlk_sigprob.lyr.geojson'
 'day4prob_nolyr|https://www.spc.noaa.gov/products/exper/day4-8/day4prob.nolyr.geojson'
 'day4prob_lyr|https://www.spc.noaa.gov/products/exper/day4-8/day4prob.lyr.geojson'
 'day1fw_dryt_nolyr|https://www.spc.noaa.gov/products/fire_wx/day1fw_dryt.nolyr.geojson'
 'day1fw_dryt_lyr|https://www.spc.noaa.gov/products/fire_wx/day1fw_dryt.lyr.geojson'
 'day1fw_windrh_nolyr|https://www.spc.noaa.gov/products/fire_wx/day1fw_windrh.nolyr.geojson'
 'day1fw_windrh_lyr|https://www.spc.noaa.gov/products/fire_wx/day1fw_windrh.lyr.geojson'
 'day2fw_dryt_nolyr|https://www.spc.noaa.gov/products/fire_wx/day2fw_dryt.nolyr.geojson'
 'day2fw_dryt_lyr|https://www.spc.noaa.gov/products/fire_wx/day2fw_dryt.lyr.geojson'
)
for item in "${urls[@]}"; do
  name=${item%%|*}
  url=${item##*|}
  out=examples/spc/${name}.geojson
  printf "Downloading %s -> %s... " "$url" "$out"
  if curl -fsS -o "$out" "$url"; then
    echo OK
  else
    echo FAIL
  fi
done
ls -1 examples/spc | wc -l
