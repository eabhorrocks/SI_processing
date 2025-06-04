import os
import shutil
from datetime import datetime
from subprocess import Popen
import sys
import shlex
import shutil


startTime = datetime.now()
print('Running runCatGTandTPrime.py...')
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))


# The first command-line argument after the script name is the mouse identifier.
mouse = sys.argv[1]
# All command-line arguments after `mouse` and before `save_date` are considered dates.
dates = sys.argv[2].split(',')   # This captures all dates as a list.
# The last command-line argument is `save_date`.
save_date = sys.argv[3]
local_folder = sys.argv[4]
no_probe = sys.argv[5]
print('Mouse: ',mouse)
print('Acquisition folders: ',dates)
#use_ks4 = sys.argv[6].lower() in ['true', '1', 't', 'y', 'yes']
#use_ks3 = sys.argv[7].lower() in ['true', '1', 't', 'y', 'yes']
pathToCatGTRunit = sys.argv[9]
pathToTPrimeRunit = sys.argv[10]
#pathToCatGTRunit = '/home/lab/CatGT-linux/runit.sh'
#pathToTPrimeRunit = '/home/lab/TPrime-linux/runit.sh'


save_folder = local_folder+ mouse +"/"
print('Local save folder: ',save_folder)
print(' ')

date_count = 0

def sorting_key(s):
    return int(s.split('_g')[-1])

if int(no_probe)>1:
    catGTprobeStr='0:' + str(no_probe)
else:
    catGTprobeStr='0'

catGTcommands = []

for date in dates: # actually acquisitions, rather than dates
    print('Current acquisiton folder:', date)
    date_count = date_count + 1
    ephys_folder = save_folder + date

    # get g files for this acquisiton
    g_files = []
    g_nums = []
    for dirname in os.listdir(ephys_folder):
        if '_g' in dirname:
            g_files.append(dirname)


    g_files = sorted(g_files, key=sorting_key)
    print('g_files found:')
    print(g_files)
    print(' ')
    firstg = sorting_key(g_files[0])
    lastg = sorting_key(g_files[-1])

    # at least 2 gfiles need to be requested for nidq.tcat to be produced?
    if lastg<1:
        lastg=1


    #print('dirtest: ',ephys_folder)

    runName = date.split('/')
    runName = mouse + '_' +runName[1]
    #print('rn: ', runName)

    cmdStr = pathToCatGTRunit + " '" \
             + '-dir=' + ephys_folder + ' -run=' + runName  \
             + ' -g=' + str(firstg) + ',' + str(lastg) + ' -t=0' + ' -t_miss_ok' + ' -zerofillmax=50' \
             + ' -prb_fld' + ' -out_prb_fld' + ' -ap' + ' -ni' + ' -prb=' + catGTprobeStr + ' -prb_miss_ok' \
             + ' -lf -lffilter=butter,12,0,500' \
             + ' -dest=' + ephys_folder + "'"

    catGTcommands.append(cmdStr)

# run CatGT commands using subprocess and wait for them to finish
print('Running CatGT...')
catgt_start_time = datetime.now()
print('CatGT OS commands:')
for cmd in catGTcommands:
    print(cmd)

procs = [Popen(shlex.split(i)) for i in catGTcommands]
for p in procs:
    p.wait()
print('CatGT finished! Time taken: ', datetime.now() - catgt_start_time)
print(' ')

# check for multiple acquisitions and join using supercat if present
nAcq = (len(dates))
if nAcq == 1:  # get the output of catGT file and finish
    date=dates[0]
    runName = date.split('/')
    tempDates = dates[0].split('/')
    outDir = save_folder +  save_date + '/' + tempDates[1] + '/' + 'catgt_' + mouse + '_' + runName[1] + '_g' + str(firstg) + '/'
    print('Final concatenated file: ')
    print(outDir)

    # if we're not running supercat we need to move some catGT files to a parent directory
    sourceDir = outDir + '/' + mouse + '_' + tempDates[1] + '_g' + str(firstg) +'_imec0/'
    file_names = os.listdir(sourceDir)
    for file_name in file_names:
        #print(file_name)
        shutil.move(os.path.join(sourceDir, file_name), outDir)
    

if nAcq > 1:  # we also want to run supercat
    
    print("Running supercat...")
    # generate catGT command line 
    cmdStr = pathToCatGTRunit + " '" \
             + '-supercat='

    for date in dates:
        ephys_folder = save_folder + date

        runName = date.split('/')
        runName = mouse + '_' + runName[1]
        cmdStr = cmdStr + '{' + ephys_folder + ',' + 'catgt_' + runName + '_g' + str(firstg) + '}'

    cmdStr = cmdStr +  ' -prb_fld -ap -ni -lf' + ' -prb=' + catGTprobeStr + ' -prb_miss_ok -supercat_trim_edges' \
             + ' -dest=' + save_folder + save_date +'/'+"'"

    # run supercat
    print('Supercat OS command: ')
    print(cmdStr)
    supercatCommands =[]
    supercatCommands.append(cmdStr)
    supercat_start_time = datetime.now()
    procs = [Popen(shlex.split(i)) for i in supercatCommands]
    for p in procs:
        p.wait()
    print('Supercat finished! Time taken: ', datetime.now() - supercat_start_time)

    # get diretory of final concatenated file
    tempDates = dates[0].split('/')
    outDir = save_folder + save_date + '/' + 'supercat_' + mouse + '_' + tempDates[1] + '_g' + str(firstg)
    print(' ')
    print('Final concatenated file: ')
    print(outDir)


catGTDir = save_folder + '/' + save_date + '/CatGToutput/'
if not os.path.exists(catGTDir):
    os.mkdir(catGTDir)

# move files to generic CatGT directory
sourceDir = outDir
file_names = os.listdir(sourceDir)
for file_name in file_names:
    #print(file_name)
    shutil.move(os.path.join(sourceDir, file_name), catGTDir)

# run TPrime
# create tprime command line - map nidaq signals to imec0

TPrimeCommands = []
tempDates = dates[0].split('/')
nidq_output_path =save_folder + '/' + save_date + '/nidq_processed/'

if os.path.exists(nidq_output_path)==False:
    os.makedirs(nidq_output_path)

lfp_output_path=save_folder + '/' + save_date + 'lfp/'

if os.path.exists(lfp_output_path)==False:
    os.makedirs(lfp_output_path)

for filename in os.listdir(catGTDir):
    if filename.endswith('lf.bin') or filename.endswith('lf.meta'):
        source_path = os.path.join(catGTDir, filename)
        destination_path = os.path.join(lfp_output_path, filename)
        shutil.move(source_path, destination_path)

print(' ')
print("Running TPrime...")
cmdStr = pathToTPrimeRunit + " '" \
        + ' -syncperiod=1.0' \
        + ' -tostream=' + catGTDir + '/' + mouse + '_' + tempDates[1] + '_g0' + '_tcat.imec0.ap.xd_384_6_500.txt' \
        + ' -fromstream=7,' + catGTDir + '/' + mouse + '_' + tempDates[1] + '_g0' + '_tcat.nidq.xd_8_3_500.txt' \
        + ' -events=7,' + catGTDir + '/' + mouse + '_' + tempDates[1] + '_g0' + '_tcat.nidq.xd_8_3_500.txt'\
        + ',' + nidq_output_path + 'nidq_sync_tprime.txt' \
        +  "'"


TPrimeCommands.append(cmdStr)
tprime_start_time = datetime.now()
procs = [Popen(shlex.split(i)) for i in TPrimeCommands]
for p in procs:
    p.wait()
print("TPrime finshed! Time taken: ", datetime.now() - tprime_start_time)
print(' ')

# move nidq.bin and 'offsets' .txt files
print("Moving the following nidq files: ")
nidq_files_to_move = []
for dirpath, dirnames, filenames in os.walk(save_folder + save_date):
    for filename in [f for f in filenames if f.endswith("_offsets.txt")]:
        nidq_files_to_move.append(os.path.join(dirpath, filename))
        print(os.path.join(dirpath, filename))

for dirpath, dirnames, filenames in os.walk(catGTDir):
    for filename in [f for f in filenames if f.endswith("tcat.nidq.bin")]:
        nidq_files_to_move.append(os.path.join(dirpath, filename))
        print(os.path.join(dirpath, filename))

for dirpath, dirnames, filenames in os.walk(catGTDir):
    for filename in [f for f in filenames if f.endswith("tcat.nidq.meta")]:
        nidq_files_to_move.append(os.path.join(dirpath, filename))
        print(os.path.join(dirpath, filename))


for file in nidq_files_to_move:
    temp = file.split('/')
    fname = temp[-1]
    shutil.move(file, os.path.join(nidq_output_path, fname))

print('runCatGTandTPrime.py finished! Time taken: ', datetime.now()-startTime)