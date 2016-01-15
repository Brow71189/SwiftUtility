# -*- coding: utf-8 -*-
"""
Created on Tue Oct  6 14:00:54 2015

@author: mittelberger
"""
from PIL import Image
import numpy as np
import os
import h5py
import struct

####################################################################################################
####################################################################################################
####################################################################################################

path = '/home/mittelberger/Documents/giacomo/ew_z_rot/0.00rad'
#offset = 69
#shape = (64, 64) # number of pixels in y, x of single frame
shape_map = (512,512) # number of pixels in map in y, x
#numbertype = np.float32
basename = 'diffAvg'
separator = '_'
save_as_hdf5 = False
save_metadata = False
####################################################################################################
####################################################################################################
####################################################################################################

integer_names = ['header_size', 'param_size', 'comment_size', 'Nx', 'Ny', 'is_complex', 'data_size', 'version']
double_names = ['t', 'dx', 'dy', 'aux_data']

def read_img(name, path=None):
    integers = {}
    doubles = {}
    comment = ''
    if path is not None:
        filename = os.path.join(path, name)
    else:
        filename = name
        
    with open(filename, mode='rb', buffering=1) as raw:
        for entry in integer_names:
            integers[entry] = struct.unpack('<i', raw.read(4))[0]
        for entry in double_names:
            if entry == 'aux_data':
                doubles[entry] = struct.unpack('<'+str(integers['param_size'])+'d', raw.read(8*integers['param_size']))
            else:
                doubles[entry] = struct.unpack('<d', raw.read(8))[0]
        comment = struct.unpack('<' + str(integers['comment_size']) + 's', raw.read(integers['comment_size']))
        
        numbertype = 'complex' + str(integers['data_size']*8) if integers['is_complex'] \
                     else 'float' + str(integers['data_size']*8)
        
        data = np.fromfile(raw, dtype=numbertype).reshape((integers['Ny'], integers['Nx']), order='F')
        
    return (data, integers, doubles, comment)

def save_file_in_hdf5(data, name, h5dataset):
    name = os.path.splitext(name)[0].split(separator)
    number = int(name[2]) + shape_map[1]*int(name[1])
    h5dataset[number] = data

def save_file_as_tiff(data, name, savepath):    
    name = os.path.splitext(name)[0].split(separator)
    savename = name[0] + separator + ('{:0' + str(len(str(np.prod(np.array(shape_map))))) + 'd}').format(int(name[2]) + \
               shape_map[1]*int(name[1])) + separator + name[1] + separator
    savename += name[2] + '.tif'

    complete_savepath = os.path.join(savepath, savename)
    # create output
    image = Image.fromarray(data)
    # save file
    image.save(complete_savepath)

if __name__ == '__main__':
    path = os.path.normpath(path)
    dirlist = os.listdir(path)
    matched_dirlist = []
    counter = 0
    
    for item in dirlist:
        if item.startswith(basename):
            matched_dirlist.append(item)
            
    savepath = os.path.normpath(path) + '_tiff'
    if not os.path.exists(savepath):
        os.makedirs(savepath)
        
    if save_metadata:
        logfile = open(os.path.join(savepath, 'logfile.txt'), mode='w')
        logfile.write('# metadata of all files in ' + path + '\n')
        logfile.write('# name\t')
        for entry in integer_names:
            logfile.write(entry + '\t')
        for entry in double_names:
            logfile.write(entry + '\t')
        logfile.write('comment\n')

    if save_as_hdf5:
        h5file = h5py.File(os.path.normpath(path)+'_h5.hdf5')
        data, integers, doubles, comment = read_img(matched_dirlist[counter], path=path)
        counter += 1
        h5dataset = h5file.create_dataset('data/science_data/data', (len(matched_dirlist), ) + 
                                         (integers['Ny'], integers['Nx']))
        if save_metadata:
            logfile.write(matched_dirlist[counter] + '\t')
            for entry in integer_names:
                logfile.write(str(integers[entry]) + '\t')
            for entry in double_names:
                logfile.write(str(doubles[entry]) + '\t')
            logfile.write(comment + '\n')
        
    print_interval = int(len(matched_dirlist)/100)
    
    print('Starting to convert {:,} files...'.format(len(matched_dirlist)))
    while counter < len(matched_dirlist):
        if counter % print_interval == 0:
            print('Processed {:,} out of {:,}...\r'.format(counter, len(matched_dirlist)), end='')
            
        data, integers, doubles, comment = read_img(matched_dirlist[counter], path=path)
        if save_metadata:
            logfile.write(matched_dirlist[counter] + '\t')
            for entry in integer_names:
                logfile.write(str(integers[entry]) + '\t')
            for entry in double_names:
                logfile.write(str(doubles[entry]) + '\t')
            logfile.write(str(comment) + '\n')
        if save_as_hdf5:
            save_file_in_hdf5(data, matched_dirlist[counter], h5dataset)
        else:
            save_file_as_tiff(data, matched_dirlist[counter], savepath)
        counter +=1 
    print('\nDone.')
    
    if save_as_hdf5:
        h5file.close()
    if save_metadata:
        logfile.close()
