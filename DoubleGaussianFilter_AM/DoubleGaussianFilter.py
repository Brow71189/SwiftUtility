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
import numpy
import scipy.fftpack

# local libraries
# None


_ = gettext.gettext


class DoubleGaussianFilterAMOperationDelegate(object):

    def __init__(self, api, fft_data_item, small_ellipse_region, big_ellipse_region, line_profile_data_item):
        self.__api = api
        self.operation_id = "double-gaussian-filter-operation_am"
        self.operation_name = _("Double Gaussian Filter AM")
        self.operation_prefix = _("Double Gaussian Filter of ")
        self.operation_description = [
            {"name": _("Sigma 1\n(large)"), "property": "sigma1", "type": "scalar", "default": 0.4},
            {"name": _("Sigma 2\n(small)"), "property": "sigma2", "type": "scalar", "default": 0.2},
            {"name": _("Weight 2"), "property": "weight2", "type": "scalar", "default": 0.3}
        ]
        self.fft_data_item = fft_data_item
        self.small_ellipse_region = small_ellipse_region
        self.big_ellipse_region = big_ellipse_region
        self.line_profile_data_item = line_profile_data_item
        

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
        intensity_calibration = data_and_metadata.intensity_calibration
        dimensional_calibrations = data_and_metadata.dimensional_calibrations
        metadata = data_and_metadata.metadata

        # grab our parameters. ideally this could just access the member variables directly,
        # but it doesn't work that way (yet).
        sigma1 = parameters.get("sigma1")**2
        sigma2 = parameters.get("sigma2")**2
        weight2 = parameters.get("weight2")

        # first calculate the FFT
        fft_data = scipy.fftpack.fftshift(scipy.fftpack.fft2(data_copy))

        # next, set up xx, yy arrays to be linear indexes for x and y coordinates ranging
        # from -width/2 to width/2 and -height/2 to height/2.
        yy_min = int(math.floor(-data.shape[0] / 2))
        yy_max = int(math.floor(data.shape[0] / 2))
        xx_min = int(math.floor(-data.shape[1] / 2))
        xx_max = int(math.floor(data.shape[1] / 2))
        xx, yy = numpy.meshgrid(numpy.linspace(yy_min, yy_max, data.shape[0]),
                                numpy.linspace(xx_min, xx_max, data.shape[1]))

        # calculate the pixel distance from the center
        rr = numpy.sqrt(numpy.square(xx) + numpy.square(yy)) / (data.shape[0] * 0.5)

        # finally, apply a filter to the Fourier space data.
        filter = numpy.exp(-0.5 * numpy.square(rr / sigma1)) - (1.0 - weight2) * numpy.exp(
            -0.5 * numpy.square(rr / sigma2))
        filtered_fft_data = fft_data * filter
        
        fft_calibration = self.__api.create_calibration(scale=1/(dimensional_calibrations[0].scale*data.shape[0]),
                                                        units='1/'+dimensional_calibrations[1].units if
                                                        dimensional_calibrations[1].units else '')
        if self.fft_data_item is None:
            self.fft_data_item = api.library.create_data_item("Filtered FFT")
        if self.line_profile_data_item is None:
            self.line_profile_data_item = api.library.create_data_item("Line Profile of Filter")
        if self.small_ellipse_region is None:
            self.small_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma2, sigma2)
        else:
            try:
                self.fft_data_item.remove_region(self.small_ellipse_region)
            except Exception as detail:
                print('Could not remove small ellipse region. Reason: ' + str(detail))
            try:
                self.small_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma2, sigma2)
            except Exception as detail:
                print('Could not add small ellipse region. Reason: ' + str(detail))
                self.fft_data_item = self.__api.library.create_data_item_from_data_and_metadata(
                                                                                self.fft_data_item.data_and_metadata,
                                                                                title="Filtered FFT")
                self.small_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma2, sigma2)
        
        if self.big_ellipse_region is None:
            self.big_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma1, sigma1)
        else:
            try:
                self.fft_data_item.remove_region(self.big_ellipse_region)
            except Exception as detail:
                print('Could not remove big ellipse region. Reason: ' + str(detail))
            try:
                self.big_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma1, sigma1)
            except Exception as detail:
                print('Could not add big ellipse region. Reason: ' + str(detail))
                self.fft_data_item = self.__api.library.create_data_item_from_data_and_metadata(
                                                                                self.fft_data_item.data_and_metadata,
                                                                                title="Filtered FFT")
                self.big_ellipse_region = self.fft_data_item.add_ellipse_region(0.5, 0.5, sigma1, sigma1)

        self.fft_data_item.set_data((numpy.log(numpy.abs(fft_data))*filter).astype(numpy.float32))
        try:
            self.line_profile_data_item.set_data((filter[filter.shape[0]/2,
                                            filter.shape[1]/2:filter.shape[1]/2*(1+2*sigma1)]).astype(numpy.float32))
        except Exception as detail:
            print('Could not change line profile data item. Reason: ' + str(detail))
            self.line_profile_data_item = self.__api.library.create_data_item_from_data_and_metadata(
                                                                        self.line_profile_data_item.data_and_metadata,
                                                                        title="Line Profile of Filter")
            self.line_profile_data_item.set_data((filter[filter.shape[0]/2, filter.shape[1]/2:]).astype(numpy.float32))
            
        self.fft_data_item.set_dimensional_calibrations([fft_calibration, fft_calibration])
        self.line_profile_data_item.set_dimensional_calibrations([fft_calibration])
        

        # and then do invert FFT and take the real value.
        result = scipy.fftpack.ifft2(scipy.fftpack.ifftshift(filtered_fft_data)).real

        return api.create_data_and_metadata_from_data(result.astype(data.dtype), intensity_calibration,
                                                      dimensional_calibrations, metadata)
        #return api.create_data_and_metadata_from_data(filtered_fft_data, intensity_calibration, dimensional_calibrations, metadata)


class DoubleGaussianAMExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.extensions.double_gaussian_am"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        self.fft_data_item = None
        self.small_ellipse_region = None
        self.big_ellipse_region = None
        self.line_profile_data_item = None
        # be sure to keep a reference or it will be closed immediately.
        self.__operation_ref = api.create_unary_operation(DoubleGaussianFilterAMOperationDelegate(api,
                                                                                        self.fft_data_item,
                                                                                        self.small_ellipse_region,
                                                                                        self.big_ellipse_region,
                                                                                        self.line_profile_data_item))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__operation_ref.close()
        self.__operation_ref = None
