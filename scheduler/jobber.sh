#Takes job id as input
# $1 -> usr_name
# $2 -> JOB_ID
# $3 -> CRC32
echo "Moving to output DIR"
cd ../upload/output_$3/
# cd /var/www/html/scheduler/Community-Finding-Tools/src/

# echo "Moved to output DIR"
# echo "Running the script."
/var/www/html/scheduler/main.py $(pwd)/input.tsv ./ >out 2>&1
echo "Ran the script."

# mv /var/www/html/scheduler/Community-Finding-Tools/src/Samples ./
# zip output.zip Samples/*
# rm -rf Samples

# echo "Moving Back to sceheduler."
cd ./../../scheduler/

# echo "Moved to scheduler and Updating Job Status."
./scheduler.py u $1 $2 4
echo $2 "is Done"