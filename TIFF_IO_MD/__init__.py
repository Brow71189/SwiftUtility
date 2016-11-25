"""
    Support for TIFF I/O.
    
    This module enables import/export of imagej compatible tif files from/to Swift.
    It will also read non-imagej tiffs, but the correct handling and shaping of multidimensional data is limited to
    files created with imagej or files that were exported with Swift.
    Files exported with Swift will keep their metadata when exported. This metadata will also be restored on re-import
    Currently the support is limited to greyscale data of 1 to 4 dimensions.
    
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
        x_resolution = y_resolution = unit = x_offset = y_offset = None
        metadata_dict = None
        data = None
        dimensional_calibrations = intensity_calibration = timestamp = data_descriptor = metadata = None
        # Imagej axes names
        images = channels = slices = frames = samples = None

        with tifffile.TiffFile(file_path) as tiffimage:
# TODO: Check whether support for multiple tif pages is necessary (for imagej compatible tifs it isn't)
            tiffpage = tiffimage.pages[0]
            # Try if image is imagej type
            if tiffimage.is_imagej:
                if tiffpage.tags.get('x_resolution') is not None:
                    x_resolution = tiffpage.tags['x_resolution'].value
                    x_resolution = x_resolution[0]/x_resolution[1]
                if tiffpage.tags.get('y_resolution') is not None:
                    y_resolution = tiffpage.tags['y_resolution'].value
                    y_resolution = y_resolution[0]/y_resolution[1]
                if tiffpage.imagej_tags.get('nion_swift') is not None:
                    metadata_dict = json.loads(tiffpage.imagej_tags['nion_swift'])
                unit = tiffpage.imagej_tags.get('unit')
                images = tiffpage.imagej_tags.get('images')
                channels = tiffpage.imagej_tags.get('channels')
                slices = tiffpage.imagej_tags.get('slices')
                frames = tiffpage.imagej_tags.get('frames')
                samples = tiffpage.imagej_tags.get('samples')
                
                    
            # Try to get swift metadata if file is not imagej type
            if metadata_dict is None:
                description = tiffpage.tags['image_description']
                try:
                    description_dict = tifffile.image_description_dict(description.value)
                except ValueError as detail:
                    print(detail)
                    description_dict = {}
                metadata_dict = description_dict.get('nion_swift')
            
            expected_number_dimensions = None
            if metadata_dict is not None:
                expected_number_dimensions = (metadata_dict.get('collection_dimension_count', 0) + 
                                              metadata_dict.get('datum_dimension_count', 1) +
                                              int(metadata_dict.get('is_sequence', False)))
                                              
            data = tiffpage.asarray()

            # number of axis in swift metadata is wrong or it could not be determined and imagej metadata is there use
            # this information to reshape array
            if (expected_number_dimensions is None or
                expected_number_dimensions != len(data.shape)) and (
                numpy.array([images, channels, slices, frames]).astype('bool').any()):
                datum_dimension_count = 1
                collection_dimension_count = 0
                is_sequence = False
                shape = numpy.array(tiffpage._shape)
                
                if channels is not None:
                    if shape[2] != channels and shape[0]/channels > 1:
                        shape[2] = channels
                        shape[0] = int(shape[0]/channels)
                    if slices is not None:
                        if shape[1] != slices and shape[0]/slices > 1:                            
                            shape[1] = slices
                            shape[0] = int(shape[0]/slices)
                
                if shape[0] > 1:
                    is_sequence = True
                if shape[1] > 1:
                    collection_dimension_count += 1
                if shape[2] > 1:
                    collection_dimension_count += 1
                if shape[3] > 1:
                    datum_dimension_count += 1
                # data should always be at least 1d, therefore we don't check for x-dimension
    
                # reshape data if shape estimate was correct
                if numpy.prod(shape) == data.size:
                    # reshape without length 1 extra dimensions
                    data = data.reshape(tuple(shape[shape>1]))
                    metadata_dict = metadata_dict if metadata_dict is not None else {}
                    metadata_dict['collection_dimension_count'] = collection_dimension_count
                    metadata_dict['datum_dimension_count'] = datum_dimension_count
                    metadata_dict['is_sequence'] = is_sequence
                    expected_number_dimensions = collection_dimension_count + datum_dimension_count + int(is_sequence)
                else:
                    print('Could not reshape data with shape ({}) to estimated shape ({})'.format(data.shape,
                                                                                                  tuple(shape)))
            
            # if number of dimensions calculated from swift metadata matches actual number of dimensions, we assume
            # that the data is still valid for being interpreted by swift shape descriptors
            if expected_number_dimensions is not None and len(data.shape) == expected_number_dimensions:
                # change axis order if necessary
                if metadata_dict.get('collection_dimension_count', 0) > 0:
                    # for 2d data in a collection we move also the second data axis
                    if metadata_dict.get('datum_dimension_count', 1) == 2:
                        data = numpy.moveaxis(data, 0, -1)
                    # for a collection we need to move the data axis to the last position
                    data = numpy.moveaxis(data, 0, -1)
            # delete shape estimators from metadata dict to avoid errors during import into Swift
            elif expected_number_dimensions is not None and metadata_dict is not None:
                print('Removed shape descriptors to avoid errors during import. ' + str(metadata_dict))
                metadata_dict.pop('collection_dimension_count', None)
                metadata_dict.pop('datum_dimension_count', None)
                metadata_dict.pop('is_sequence', None)
            
# TODO: Add rgb(a) data support
#        if data.dtype == numpy.uint8 and data.shape[-1] == 3 and len(data.shape) > 1:
#            data = data[:,:,(2, 1, 0)]
#        if data.dtype == numpy.uint8 and data.shape[-1] == 4 and len(data.shape) > 1:
#            data = data[:,:,(2, 1, 0, 3)]

        # remove calibrations if their number is wrong
        if dimensional_calibrations is not None and len(dimensional_calibrations) != len(data.shape):
            dimensional_calibrations = None
        # If no dimensional calibrations were found in the swift metadata, try to use imagej calibrations
        if dimensional_calibrations is None:
            # if swift metadata is there try to assign calibrations to the correct axis
            if metadata_dict is not None:
                # If data is a collection, assume x- and y-calibration for collection axis
                if metadata_dict.get('collection_dimension_count', 0) > 0:
                    # for 1d-collection assume we want x-resolution
                    if metadata_dict['collection_dimension_count'] == 1:
                        dimensional_calibrations = [self.__api.create_calibration(offset=x_offset,
                                                        scale=(1/x_resolution) if x_resolution else None,
                                                        units=unit)]
    
                    elif metadata_dict['collection_dimension_count'] == 2:
                        dimensional_calibrations = [self.__api.create_calibration(offset=y_offset,
                                                        scale=(1/y_resolution) if y_resolution else None,
                                                        units=unit),
                                                    self.__api.create_calibration(offset=x_offset,
                                                        scale=(1/x_resolution) if x_resolution else None,
                                                        units=unit)]
                    # Add "empty" calibrations for remaining axis
                    number_calibrations = len(dimensional_calibrations)
                    for i in range(len(data.shape) - number_calibrations):
                        dimensional_calibrations.append(self.__api.create_calibration())
                else:
                    # Assume that x- and y-calibration is for data
                    if metadata_dict.get('datum_dimension_count', 1) == 1:
                        dimensional_calibrations = [self.__api.create_calibration(offset=x_offset,
                                                        scale=(1/x_resolution) if x_resolution else None,
                                                        units=unit)]
                    elif metadata_dict.get('datum_dimension_count', 1) == 2:
                        dimensional_calibrations = [self.__api.create_calibration(offset=y_offset,
                                                        scale=(1/y_resolution) if y_resolution else None,
                                                        units=unit),
                                                    self.__api.create_calibration(offset=x_offset,
                                                        scale=(1/x_resolution) if x_resolution else None,
                                                        units=unit)]
                    # If calibrations were created, make sure their number is correct
                    if dimensional_calibrations is not None:
                        number_calibrations = len(dimensional_calibrations)
                        for i in range(len(data.shape) - number_calibrations):
                            dimensional_calibrations.insert(0, self.__api.create_calibration())
            # If no swift metadata is there use calibrations for guessed axes
            else:
                # Data will be at least 1D so we can append x-calibration in any case
                dimensional_calibrations = [self.__api.create_calibration(offset=x_offset,
                                            scale=(1/x_resolution) if x_resolution else None,
                                            units=unit)]
                # If data has more dimensions also append y-resolution
                dimensional_calibrations.insert(0, self.__api.create_calibration(offset=y_offset,
                                                   scale=(1/y_resolution) if y_resolution else None,
                                                   units=unit))
                # Add "empty" calibrations for remaining axes
                number_calibrations = len(dimensional_calibrations)
                for i in range(len(data.shape) - number_calibrations):
                    dimensional_calibrations.insert(0, self.__api.create_calibration())
        
        # create Swift data descriptors
        if metadata_dict is not None:
            dimensional_calibrations, intensity_calibration, timestamp, data_descriptor, metadata = (
                                                       self.create_data_descriptors_from_metadata_dict(metadata_dict))
        
        # If data is 3d and no swift metadata was found make is_sequence True because a stack of images will be the
        # most likely case of imported 3d data
        if data_descriptor is None and len(data.shape) == 3:
            data_descriptor = self.__api.create_data_descriptor(True, 0, 2)
        print(dimensional_calibrations, intensity_calibration, timestamp, data_descriptor, metadata)
        data_and_metadata = self.__api.create_data_and_metadata(data, intensity_calibration, dimensional_calibrations,
                                                                metadata, timestamp, data_descriptor)
        return data_and_metadata

    def can_write_data_and_metadata(self, data_and_metadata, extension):
        #return data_and_metadata.is_data_2d or data_and_metadata.is_data_1d or data_and_metadata.is_data_3d
        return len(data_and_metadata.data_shape) < 5

    def write_data_and_metadata(self, data_and_metadata, file_path, extension):    
        data = data_and_metadata.data
        #metadata = data_and_metadata.metadata
        resolution = None
        unit = None
        tifffile_metadata={'kwargs': {}}
        
        calibrations = data_and_metadata.dimensional_calibrations

        tifffile_metadata['kwargs']['unit'] = ''
        metadata_dict = self.extract_metadata_dict_from_data_and_metadata(data_and_metadata)
        tifffile_metadata['kwargs']['nion_swift'] = json.dumps(metadata_dict)
                    
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
                    resolution += (1/calibrations[-2].scale, ) if calibrations[-2].scale != 0 else (1, )
            
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
            
            data = data.reshape(tuple(tifffile_shape))
            
            # Change dtype if necessary to make tif compatible with imagej
            if not data.dtype in [numpy.float32, numpy.uint8, numpy.uint16]:
                data = data.astype(numpy.float32)
            try:
                tifffile.imsave(file_path, data, resolution=resolution, imagej=True, metadata=tifffile_metadata, software='Nion Swift')
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
        if not None in [metadata_dict.get('collection_dimension_count'), metadata_dict.get('datum_dimension_count')]:
            data_descriptor = self.__api.create_data_descriptor(metadata_dict.get('is_sequence', False), metadata_dict.get('collection_dimension_count'), metadata_dict.get('datum_dimension_count'))
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

