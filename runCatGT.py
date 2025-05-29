import os
import shutil
from datetime import datetime
from subprocess import Popen
import sys
import shlex


startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))

# The first command-line argument after the script name is the mouse identifier.
#mouse='M24019' #mouse id
#save_date='20240716' #date of recording
#dates='20240716/20240716_0,20240716/20240716_2' #acquisition date and session e.g. dates='20240624/20240624_0,20240624/20240624_1'
#base_folder='/home/lab/spikeinterface_sorting/temp_data/'  # Adjust this path if necessary
#local_folder = base_folder
#no_probe=1 #number of probes you have in this session

# The first command-line argument after the script name is the mouse identifier.
mouse = sys.argv[1]
# All command-line arguments after `mouse` and before `save_date` are considered dates.
dates = sys.argv[2].split(',')   # This captures all dates as a list.
# The last command-line argument is `save_date`.
save_date = sys.argv[3]
local_folder = sys.argv[4]
no_probe = sys.argv[5]
print(mouse)
print('acquisition folder: ',dates)
#use_ks4 = sys.argv[6].lower() in ['true', '1', 't', 'y', 'yes']
#use_ks3 = sys.argv[7].lower() in ['true', '1', 't', 'y', 'yes']
base_folder = '/mnt/rds01/ibn-vision/DATA/SUBJECTS/'

save_folder = local_folder+ mouse +"/"
print('save folder: ',save_folder)

nAcq = (len(dates))
date_count = 0
pathToRunit = '/home/lab/CatGT-linux/runit.sh'


osCommands = []

catGTcommands = []

for date in dates:
    print('acquisition folder:',date)
    date_count = date_count + 1
    ephys_folder = save_folder + date
    #print('dirtest: ',ephys_folder)

    runName = date.split('/')
    runName = mouse + '_' +runName[1]
    #print('rn: ', runName)




    cmdStr = pathToRunit + " '" \
             + '-dir=' + ephys_folder + ' -run=' + runName  \
             + ' -g=0,100' + ' -t=0' + ' -t_miss_ok' + ' --zerofillmax=50' \
             + ' -prb_fld' + ' -out_prb_fld' + ' -ap' + ' -ni' + ' -prb=0:1' + ' -prb_miss_ok' \
             + ' -dest=' + ephys_folder + "'"

    catGTcommands.append(cmdStr)


print('CatGT OS commands:')
print(catGTcommands[0])
print(catGTcommands[1])

procs = [Popen(shlex.split(i)) for i in catGTcommands]
for p in procs:
    p.wait()

if nAcq == 1:  # get the output of catGT file and finish
    date=dates[0]
    runName = date.split('/')
    baseDate = runName[0]
    tempDates = dates[0].split('/')
    outDir = save_folder + 'ephys' + '/' + dates[0] + '/' + 'catgt_' + runName[1] + '_g0'
    print('Final concatenated file: ')
    print(outDir)

if nAcq > 1:  # we also want to run supercat
    print("running supercat ")

    cmdStr = pathToRunit + " '" \
             + '-supercat='

    for date in dates:
        ephys_folder = save_folder + date

        runName = date.split('/')
        baseDate = runName[0]
        runName = mouse + '_' + runName[1]
        cmdStr = cmdStr + '{' + ephys_folder + '/' + ',' + 'catgt_' + runName + '_g0' + '}'

    cmdStr = cmdStr +  ' -prb_fld -ap -ni -prb=0:1 -prb_miss_ok -supercat_trim_edges -dest=' + save_folder + baseDate +'/'+"'"

    print('Supercat command: ')
    print(cmdStr)
    supercatCommands =[]
    supercatCommands.append(cmdStr)
    procs = [Popen(shlex.split(i)) for i in supercatCommands]
    for p in procs:
        p.wait()

    # get diretory of final concatenated file
    tempDates = dates[0].split('/')
    outDir = save_folder + baseDate + '/' + 'supercat_' + mouse + '_' + tempDates[1] + '_g0';
    print('Final concatenated file: ')
    print(outDir)

