# The Buffer

The "buffer" contains a CSV file for each pipeline execution with the following name: `<execution id><pipeline_slug>_buffer.csv`

This CSV files are ephimeral and live only during their respective execution.

They act like a buffer because each transformation will initially feed from it but will end up dumping the transformed data into it all over again.

The algorithms works like a reduction or series of middlewares.
