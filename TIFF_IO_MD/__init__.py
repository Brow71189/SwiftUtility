"""
    Support for TIFF I/O.
"""

# standard libraries
import gettext
import warnings
import logging

# third party libraries
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from TIFF_IO_MD import tifffile
import numpy
import datetime
import json

# local libraries



_ = gettext.gettext


class TIFFIODelegate(object):

    def __init__(self, api):
        self.__api = api
        self.io_handler_id = "tiff-io-handler"
        self.io_handler_name = _("TIFF Files")
        self.io_handler_extensions = ["tif", "tiff"]

    def read_data_and_metadata(self, extension, file_path):
        import traceback
        traceback.print_stack()
        x_resolution = y_resolution = 1
        unit = ''
        metadata_dict = None
        with tifffile.TiffFile(file_path) as tiffimage:
            if tiffimage.is_imagej:
                try:
                    tiffpage = tiffimage.pages[0]
                    tiffpage._patch_imagej()
                    x_resolution = tiffpage.tags['x_resolution'].value
                    y_resolution = tiffpage.tags['y_resolution'].value
                    x_resolution = x_resolution[0]/x_resolution[1]
                    y_resolution = y_resolution[0]/y_resolution[1]
                    description = tiffpage.tags['image_description'].value.decode()
                    description = description.split()
                    print(tiffpage.imagej_tags)
                    if tiffpage.imagej_tags.get('nion_swift') is not None:
                        print(tiffpage.imagej_tags['nion_swift'])
                        metadata_dict = json.loads(tiffpage.imagej_tags['nion_swift'])
                            
                    unit = ''
                    for element in description:
                        if element.startswith('unit'):
                            element = element.split('=')
                            unit = element[1]                        
                except Exception as detail:
                    print('Could not get tiff metadata. Reason: ' + str(detail))
                    x_resolution = y_resolution = 1
                    unit = ''
            else:
                print('Image seems not to be created with imagej. Could not get metadata.')
        
        print(str(x_resolution), str(y_resolution), unit)
        data = tifffile.imread(file_path)
        print(data.shape)
            
            
        if data.dtype == numpy.uint8 and data.shape[-1] == 3 and len(data.shape) > 1:
            data = data[:,:,(2, 1, 0)]
        if data.dtype == numpy.uint8 and data.shape[-1] == 4 and len(data.shape) > 1:
            data = data[:,:,(2, 1, 0, 3)]
        
        dimensional_calibrations, intensity_calibration, timestamp, data_descriptor, metadata = self.create_data_descriptors_from_metadata_dict(metadata_dict)

#        dimensional_calibrations = [self.__api.create_calibration(offset=0.0, scale=1/y_resolution, units=unit),
#                                    self.__api.create_calibration(offset=0.0, scale=1/x_resolution, units=unit)]
#        data_shape_and_dtype = Image.dimensional_shape_from_data(data), data.dtype
#        data_and_metadata = self.__api.create_data_and_metadata_from_data(data, dimensional_calibrations=dimensional_calibrations)
        print(dimensional_calibrations, intensity_calibration, timestamp, data_descriptor, metadata)
        data_and_metadata = self.__api.create_data_and_metadata(data, intensity_calibration, dimensional_calibrations,
                                                                metadata, timestamp, data_descriptor)
        return data_and_metadata

    def can_write_data_and_metadata(self, data_and_metadata, extension):
        return data_and_metadata.is_data_2d or data_and_metadata.is_data_1d or data_and_metadata.is_data_3d

    def write_data_and_metadata(self, data_and_metadata, file_path, extension):    
        data = data_and_metadata.data
        #metadata = data_and_metadata.metadata
        resolution = None
        unit = None
        tifffile_metadata={'kwargs': {}}
        
#        # Check and adapt for metadata that was imported        
#        if metadata.get('hardware_source').get('imported_properties'):
#            metadata = metadata['hardware_source']['imported_properties']
#        
#        # Check if data item has metadata and if FOV is in it
#        if metadata.get('hardware_source'):
#            if metadata['hardware_source'].get('hardware_source_id') == 'superscan':
#                if metadata['hardware_source'].get('fov_nm'):
#                    fov = metadata['hardware_source'].get('fov_nm')
#                    resolution = tuple(numpy.array(data.shape)[:2] / numpy.array((fov, fov)))
#                    tifffile_metadata['kwargs']['unit'] = 'nm'
        calibrations = data_and_metadata.dimensional_calibrations
#        resolution = tuple()
        tifffile_metadata['kwargs']['unit'] = ''
        metadata_dict = self.extract_metadata_dict_from_data_and_metadata(data_and_metadata)
        tifffile_metadata['kwargs']['nion_swift'] = json.dumps(metadata_dict)
        
#        calibrations.reverse()
#        for calibration in calibrations:
#            if calibration.scale != 0:
#                resolution += (1/calibration.scale, )
#            else:
#                resolution += (1,)
#            if not calibration.units in tifffile_metadata['kwargs']['unit']:
#                tifffile_metadata['kwargs']['unit'] += calibration.units
        # get correct x- and y-spatial calibrations depending on data descriptors and add them to tiff

                    
        if data is not None:
#            if data.dtype == numpy.uint8 and data.shape[-1] == 3 and len(data.shape) > 1:
#                data = data[:,:,(2, 1, 0)]
#            if data.dtype == numpy.uint8 and data.shape[-1] == 4 and len(data.shape) > 1:
#                data = data[:,:,(2, 1, 0, 3)]
#            if not (data.dtype == numpy.float32 or data.dtype == numpy.uint8 or data.dtype == numpy.uint16):
#                data = data.astype(numpy.float32)

# TODO: support data that is a sequence AND a collection
# TODO: handle rgb(a) data
                
            # create shape that is used for tif so that array is interpreted correctly by imagej
            tifffile_shape = numpy.ones(6, dtype=numpy.int)
            if data_and_metadata.collection_dimension_count > 0:
                # if data is a collection, put collection axis in x-and y of tif
                tifffile_shape[4] = data.shape[0]
                # use collection x-calibration as x-calibration in tif
                resolution = (1/calibrations[0].scale, ) if calibrations[0].scale != 0 else (1, )
                # use x-unit in tif (unfortunately there is no way to save separate units for x- and y)
                unit = calibrations[0].units
                # if data is a 2d-collection, also fill y-axis of tif
                if data_and_metadata.collection_dimension_count == 2:
                    tifffile_shape[3] = data.shape[1]
                    # add collection y-calibration as y-calibration in tif
                    resolution += (1/calibrations[1].scale, ) if calibrations[1].scale != 0 else (1, )
                # for data x-axis use tif "channel" axis
                tifffile_shape[2] = data.shape[-1]
                # if data is 2d, put y-axis in tif z-axis (there is no better option unfortunately)
                if data_and_metadata.datum_dimension_count == 2:
                    tifffile_shape[1] = data.shape[-2]
            else:
                if data_and_metadata.is_sequence:
                    # Put sequence axis in "time" axis of tif
                    tifffile_shape[0] = data.shape[0]
                # data x-axis goes in tif x-axis
                tifffile_shape[4] = data.shape[-1]
                # use data x-calibration as x-calibration in tif
                resolution = (1/calibrations[-1].scale, ) if calibrations[-1].scale != 0 else (1, )
                # use x-unit in tif (unfortunately there is no way to save separate units for x- and y)
                unit = calibrations[-1].units
                # if data is 2d, also put y-axis there
                if data_and_metadata.datum_dimension_count == 2:
                    tifffile_shape[3] = data.shape[-2]
                    # use data y-calibration as y-calibration in tif
                    resolution = (1/calibrations[-2].scale, ) if calibrations[-2].scale != 0 else (1, )
            
            # change axis order if necessary
            if data_and_metadata.collection_dimension_count > 0:
                # for a collection we need to move the data axis in front of collection axis
                data = numpy.moveaxis(data, -1, 0)
                # for 2d data also move the second data axis in front
                if data_and_metadata.datum_dimension_count == 2:
                    data = numpy.moveaxis(data, -1, 0)
            
            # make sure "resolution" is always a 2-tuple
            if resolution is not None and len(resolution) < 2:
                resolution += (1,)
            # add unit to tif tags
            if unit is not None:
                tifffile_metadata['kwargs']['unit'] = unit
            
                    
            print(tifffile_shape)
            data = data.reshape(tuple(tifffile_shape))
#            if len(data.shape) == 1:
#                data = data.reshape((1,) + data.shape)
#                resolution = resolution + resolution
            
            # Change dtype if necessary to make tif compatible with imagej
            if not (data.dtype == numpy.float32 or data.dtype == numpy.uint8 or data.dtype == numpy.uint16):
                data = data.astype(numpy.float32)
            try:
                tifffile.imsave(file_path, data, resolution=resolution, imagej=True, metadata=tifffile_metadata)
            except Exception as detail:
                tifffile.imsave(file_path, data, resolution=resolution, metadata=tifffile_metadata['kwargs'])
                logging.warn('Could not save metadata in tiff. Reason: ' + str(detail))
                
    def extract_metadata_dict_from_data_and_metadata(self, data_and_metadata):
        metadata_dict = {}
        dimensional_calibrations = data_and_metadata.dimensional_calibrations
        if dimensional_calibrations is not None:
            calibrations_element = []
            for calibration in dimensional_calibrations:
                calibrations_element.append({'offset': calibration.offset, 'scale': calibration.scale,
                                             'units': calibration.units})
            metadata_dict['spatial_calibrations'] = calibrations_element
        intensity_calibration = data_and_metadata.intensity_calibration
        if intensity_calibration is not None:
            metadata_dict['intensity_calibration'] = {'offset': intensity_calibration.offset,
                                                      'scale': intensity_calibration.scale,
                                                      'units': intensity_calibration.units}
        if data_and_metadata.is_sequence:
            metadata_dict['is_sequence'] = data_and_metadata.is_sequence
        metadata_dict['collection_dimension_count'] = data_and_metadata.collection_dimension_count
        metadata_dict['datum_dimension_count'] = data_and_metadata.datum_dimension_count
        metadata_dict['properties'] = dict(data_and_metadata.metadata.get('hardware_source', {}))
        metadata_dict['timestamp'] = data_and_metadata.timestamp.timestamp()
        return metadata_dict
        
    def create_data_descriptors_from_metadata_dict(self, metadata_dict):
        dimensional_calibrations = intensity_calibration = timestamp = data_descriptor = metadata = None
        if metadata_dict.get('spatial_calibrations') is not None:
            dimensional_calibrations = []
            for calibration in metadata_dict['spatial_calibrations']:
                dimensional_calibrations.append(self.__api.create_calibration(offset=calibration.get('offset'), scale=calibration.get('scale'), units=calibration.get('units')))
        if metadata_dict.get('intensity_calibration') is not None:
            calibration = metadata_dict['intensity_calibration']
            intensity_calibration = self.__api.create_calibration(offset=calibration.get('offset'),  scale=calibration.get('scale'), units=calibration.get('units'))
            print([metadata_dict.get('collection_dimension_count'), metadata_dict.get('datum_dimension_count'), metadata_dict.get('is_sequence')])
        if not None in [metadata_dict.get('collection_dimension_count'), metadata_dict.get('datum_dimension_count')]:
            data_descriptor = self.__api.create_data_descriptor(metadata_dict.get('is_sequence', False), metadata_dict.get('collection_dimension_count'), metadata_dict.get('datum_dimension_count'))
            #data_descriptor = self.__api.create_data_descriptor(True, 0, 1)
        if metadata_dict.get('properties') is not None:
            metadata = {'hardware_source': metadata_dict['properties']}
        if metadata_dict.get('timestamp') is not None:
            timestamp = datetime.datetime.fromtimestamp(metadata_dict['timestamp'])
        return dimensional_calibrations, intensity_calibration, timestamp, data_descriptor, metadata

class TIFFIOExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.extensions.tiff_io"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__io_handler_ref = api.create_data_and_metadata_io_handler(TIFFIODelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__io_handler_ref.close()
        self.__io_handler_ref = None

