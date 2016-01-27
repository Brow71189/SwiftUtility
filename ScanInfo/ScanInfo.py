# standard libraries
import gettext
import logging

_ = gettext.gettext

class ScanMapPanelDelegate(object):
    
    
    def __init__(self, api):
        self.__api = api
        self.panel_id = 'ScanInfo-Panel'
        self.panel_name = _('ScanInfo')
        self.panel_positions = ['left', 'right']
        self.panel_position = 'right'
        self.adocument_controller = None
        self.switches = {'show_all': False}
        self._checkboxes = {}
    
    def create_panel_widget(self, ui, document_controller):
                
        def checkbox_changed(check_state):
            for key, value in self._checkboxes.items():
                self.switches[key] = value.checked
       
        def show_button_clicked():
            if self.adocument_controller == None:
                self.adocument_controller = self.__api.application.document_controllers[0]
            metadata = self.adocument_controller.target_data_item.metadata
            
            if not metadata.get('hardware_source'):
                logging.info('Could not find any metadata in the selected data item. Maybe it is processed data.')
                return

            logging.info('\nMetadata of currently selected data item:\n')
            
            if metadata['hardware_source'].get('hardware_source_id') == 'superscan' and not self.switches['show_all']:
                showkeys = ['channel_name', 'pixel_time_us', 'fov_nm', 'rotation_deg', 'center_x_nm', 'center_y_nm']
                for key in showkeys:
                    logging.info(key + ':\t' + str(metadata['hardware_source'].get(key)))
            
            else:
                for key, value in metadata['hardware_source'].items():
                    logging.info(key + ':\t' + str(value))
            
            logging.info('\n')
        
        column = ui.create_column_widget()
        description = ui.create_label_widget('Shows metadata for selected data item.')
        show_all_checkbox = ui.create_check_box_widget('Show all metadata ')
        show_all_checkbox.on_check_state_changed = checkbox_changed
        show_button = ui.create_push_button_widget('Show')
        show_button.on_clicked = show_button_clicked
        
        description_row = ui.create_row_widget()
        checkbox_row = ui.create_row_widget()
        button_row = ui.create_row_widget()
        
        description_row.add(description)
        description_row.add_stretch()
        checkbox_row.add(show_all_checkbox)
        checkbox_row.add_stretch()
        button_row.add(show_button)
        
        column.add(description_row)
        column.add(checkbox_row)
        column.add(button_row)
        column.add_stretch()
        
        self._checkboxes['show_all'] = show_all_checkbox

        return column
        
        
class ScanMapExtension(object):
    extension_id = 'univie.scaninfo'
    
    def __init__(self, api_broker):
        api = api_broker.get_api(version='1', ui_version='1')
        self.__panel_ref = api.create_panel(ScanMapPanelDelegate(api))
    
    def close(self):
        self.__panel_ref.close()
        self.__panel_ref = None