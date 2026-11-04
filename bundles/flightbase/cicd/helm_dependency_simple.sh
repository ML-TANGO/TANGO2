cd ./helm
helm dependency build
cd ..

# May not be used at CI/CD on its chart
# but used in ../parse_then_resursive.sh call