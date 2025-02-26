#!/bin/bash

# Specify the input file containing arXiv IDs, one per line
input_file="ids_with_cs_ai.txt"

# Check if the input file exists
if [ ! -f "$input_file" ]; then
    echo "Error: Input file '$input_file' not found."
    exit 1
fi

# Loop through each ID in the input file
while IFS= read -r id; do
    # Skip empty lines
    if [ -z "$id" ]; then
        continue
    fi
    
    # Extract the prefix (everything before the first dot)
    prefix=$(echo "$id" | cut -d '.' -f 1)
    
    # Construct the gsutil command
    gsutil cp "gs://arxiv-dataset/arxiv/arxiv/pdf/${prefix}/${id}.pdf" ./pdf/
    
done < "$input_file"

echo "All PDFs have been downloaded."