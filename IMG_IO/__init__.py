"""
    Support for TIFF I/O.
"""

# standard libraries
import gettext
import warnings

# third party libraries
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from IMG_IO import convert_img
#import numpy

# local libraries
# None


_ = gettext.gettext


class IMGIODelegate(object):

    def __init__(self, api):
        self.__api = api
        self.io_handler_id = "img-io-handler"
        self.io_handler_name = _("QSTEM")
        self.io_handler_extensions = ["img"]

    def read_data_and_metadata(self, extension, file_path):
        data, integers, doubles, comment = convert_img.read_img(file_path)
        doubles.pop('aux_data')
        print(integers)
        print(doubles)
        print(comment)
        dimensional_calibrations = [self.__api.create_calibration(offset=0.0, scale=doubles['dy']/10.0, units='nm'),
                                    self.__api.create_calibration(offset=0.0, scale=doubles['dx']/10.0, units='nm')]
        return self.__api.create_data_and_metadata(data, dimensional_calibrations=dimensional_calibrations)

    def can_write_data_and_metadata(self, data_and_metadata, extension):
        return False
        

class IMGIOExtension(object):

    # required for Swift to recognize this as an extension class.
    extension_id = "nion.swift.extensions.img_io"

    def __init__(self, api_broker):
        # grab the api object.
        api = api_broker.get_api(version="1", ui_version="1")
        # be sure to keep a reference or it will be closed immediately.
        self.__io_handler_ref = api.create_data_and_metadata_io_handler(IMGIODelegate(api))

    def close(self):
        # close will be called when the extension is unloaded. in turn, close any references so they get closed. this
        # is not strictly necessary since the references will be deleted naturally when this object is deleted.
        self.__io_handler_ref.close()
        self.__io_handler_ref = None