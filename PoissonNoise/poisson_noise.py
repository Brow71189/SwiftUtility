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


class PoissonOperationDelegate(object):

    def __init__(self, api):
        self.__api = api
        self.operation_id = "poisson-operation"
        self.operation_name = _("Add Poisson Noise")
        self.operation_prefix = _("Possion Noised ")
        self.operation_description = [
            {"name": "Mean", "property": "mean", "type": "scalar", "default": 0.1},
            {"name": "Background", "property": "background", "type": "scalar", "default": 0.1}
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
        mean = parameters.get("mean")**2*100 + 1
        background = parameters.get("background")**2*10
        
        current_mean = np.mean(data_copy)

        # Add background to image
        offset = background*current_mean
        data_copy += offset
        
        # Calculate scale that is necessary to adjust mean of image
        #current_mean = np.mean(data_copy)
        scale = mean/current_mean
        
        # Scale image
        data_copy *= scale
        
        # Add Noise
        result = np.random.poisson(lam=data_copy.flatten(), size=np.size(data_copy)).astype(data.dtype)
        
        # Reshape result
        result = np.reshape(result, data_copy.shape)
        
        # Scale back
        result /= scale
        result -= offset
        
        intensity_calibration = data_and_metadata.intensity_calibration
        dimensional_calibrations = data_and_metadata.dimensional_calibrations
        metadata = data_and_metadata.metadata
        
        return api.create_data_and_metadata_from_data(result, intensity_calibration,
                                                      dimensional_calibrations, metadata)


class PoissonExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.extensions.poisson"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__operation_ref = api.create_unary_operation(PoissonOperationDelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__operation_ref.close()
        self.__operation_ref = None
