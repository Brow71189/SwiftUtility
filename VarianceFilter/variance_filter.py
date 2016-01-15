"""
    Double Gaussian Filter.

    Implemented as an operation that can be applied to data items.

    This code is experimental, meaning that it works with the current version
    but will probably not work "as-is" with future versions of the software.

"""

# standard libraries
import gettext
import math

# third party libraries
import numpy as np
import scipy.fftpack
from scipy.ndimage import uniform_filter, gaussian_filter

# local libraries
# None


_ = gettext.gettext


class VarianceFilterOperationDelegate(object):

    def __init__(self, api):
        self.__api = api
        self.operation_id = "variance-operation"
        self.operation_name = _("Variance Filter")
        self.operation_prefix = _("Variance Filter of ")
        self.operation_description = [
            {"name": _("Radius"), "property": "radius", "type": "scalar", "default": 0.1},
        ]

    def can_apply_to_data(self, data_and_metadata):
        return data_and_metadata.is_data_2d and data_and_metadata.is_data_scalar_type

    # process is called to process the data. this version does not change the data shape
    # or data type. if it did, we would need to provide another function to describe the
    # change in shape or data type.
    def get_processed_data_and_metadata(self, data_and_metadata, parameters):
        api = self.__api

        # only works with 2d, scalar data
        assert data_and_metadata.is_data_2d
        assert data_and_metadata.is_data_scalar_type

        # make a copy of the data so that other threads can use data while we're processing
        # otherwise numpy puts a lock on the data.
        data = data_and_metadata.data
        data_copy = data.copy()

        # grab our parameters. ideally this could just access the member variables directly,
        # but it doesn't work that way (yet).
        radius = parameters.get("radius")*100
        #sigma2 = parameters.get("sigma2")
        #weight2 = parameters.get("weight2")
        
        # Apply mean filter to the data
        data_copy = uniform_filter(data_copy, size=radius)
        
        # Calculate squared differences from original
        result = np.square(data_copy - data)
        
        # Apply mean filter to the result
        #result = gaussian_filter(result, radius)/data_copy
        result = uniform_filter(result, size=radius)/data_copy

        intensity_calibration = data_and_metadata.intensity_calibration
        dimensional_calibrations = data_and_metadata.dimensional_calibrations
        metadata = data_and_metadata.metadata
        return api.create_data_and_metadata_from_data(result, intensity_calibration, dimensional_calibrations, metadata)


class VarianceExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.extensions.variance"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__operation_ref = api.create_unary_operation(VarianceFilterOperationDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__operation_ref.close()
        self.__operation_ref = None
