
# get all the recordings on that day
# allocate destination folder and move the ephys folder on the server to Beast lab user

import os
import os.path
from shutil import copytree, ignore_patterns


from datetime import datetime
import sys



import scipy.io as sio
startTime = datetime.now()
print('Start Time:' + startTime.strftime("%m/%d/%Y, %H:%M:%S"))
''' this section defines the animal and dates and fetch the recordings from the server to Beast'''

# The first command-line argument after the script name is the mouse identifier.
mouse = sys.argv[1]
# All command-line arguments after `mouse` and before `save_date` are considered dates.
dates = sys.argv[2].split(',')  # This captures all dates as a list.
# The last command-line argument is `save_date`.
save_date = sys.argv[3]
local_folder = sys.argv[4]
no_probe = sys.argv[5]
use_ks4 = sys.argv[6].lower() in ['true', '1', 't', 'y', 'yes']
use_ks3 = sys.argv[7].lower() in ['true', '1', 't', 'y', 'yes']
server_folder = '/mnt/rds01/ibn-vision/DATA/SUBJECTS/'
save_folder = local_folder + mouse + "/"
save_folder2=save_folder+save_date

# get the final output folder of CatGT
nAcq = (len(dates))

if nAcq == 1:
    date=dates[0]
    runName = date.split('/')
    tempDates = dates[0].split('/')
    outDir = save_folder +  save_date + '/' + tempDates[1] + '/' + 'catgt_' + mouse + '_' + runName[1] + '_g0/'
    save_folder = outDir

if nAcq > 1:
    date = dates[0]
    runName = date.split('/')
    baseDate = runName[0]
    tempDates = dates[0].split('/')
    outDir = save_folder + baseDate + '/' + 'supercat_' + mouse + '_' + tempDates[1] + '_g0/'
    print('Final concatenated file: ')
    print(outDir)
    save_folder = outDir


# Copy files
destDir = server_folder + mouse + '/ephys/' + save_date
nidqDir = save_folder2 + '/nidq_processed/'
print('Copying files to server...')
print('server destination: ', destDir)
print('Copying nidq files to ', destDir+'/nidq_processed/')
copytree(nidqDir, destDir+'/nidq_processed/') 
print('Copying spike-sorting files to ', destDir+'/spike_sorting/')

for probe in range(int(no_probe)): 
    folders_to_move = ['probe'+str(probe), 'probe'+str(probe)+'_preprocessed']

    for folder in folders_to_move:
            copytree(outDir + folder, destDir+'/spike_sorting/' + folder, ignore=ignore_patterns('*bin', '*.raw', '*.dat'))


print('All Done! Overall it took:')

print(datetime.now() - startTime)
print('Please delete local files!')

sys.exit(0)