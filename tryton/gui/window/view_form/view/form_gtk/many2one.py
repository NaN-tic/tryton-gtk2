#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
import gtk
import gobject
import gettext

from .widget import Widget
import tryton.common as common
from tryton.gui.window.view_form.screen import Screen
from tryton.gui.window.win_search import WinSearch
from tryton.gui.window.win_form import WinForm
from tryton.common.popup_menu import populate
from tryton.common.completion import get_completion, update_completion
from tryton.common.entry_position import manage_entry_position

_ = gettext.gettext


class Many2One(Widget):

    def __init__(self, view, attrs):
        super(Many2One, self).__init__(view, attrs)

        self.widget = gtk.HBox(spacing=0)
        self.widget.set_property('sensitive', True)

        self.wid_text = gtk.Entry()
        self.wid_text.set_property('width-chars', 13)
        self.wid_text.set_property('activates_default', True)
        self.wid_text.connect('key-press-event', self.send_modified)
        self.wid_text.connect('key_press_event', self.sig_key_press)
        self.wid_text.connect('populate-popup', self._populate_popup)
        self.wid_text.connect('focus-out-event',
            lambda x, y: self._focus_out())
        self.wid_text.connect('changed', self.sig_changed)
        manage_entry_position(self.wid_text)
        self.changed = True
        self.focus_out = True

        if int(self.attrs.get('completion', 1)):
            self.wid_completion = get_completion()
            self.wid_completion.connect('match-selected',
                self._completion_match_selected)
            self.wid_completion.connect('action-activated',
                self._completion_action_activated)
            self.wid_text.set_completion(self.wid_completion)
            self.wid_text.connect('changed', self._update_completion)
        else:
            self.wid_completion = None

        self.wid_text.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY,
            'tryton-find')
        self.wid_text.connect('icon-press', self.sig_edit)

        self.widget.pack_start(self.wid_text, expand=True, fill=True)
        self.widget.set_focus_chain([self.wid_text])

        self._readonly = False

    def get_model(self):
        return self.attrs['relation']

    def _readonly_set(self, value):
        self._readonly = value
        self._set_button_sensitive()
        if value:
            self.widget.set_focus_chain([])
        else:
            self.widget.set_focus_chain([self.wid_text])

    def _set_button_sensitive(self):
        self.wid_text.set_editable(not self._readonly)
        self.wid_text.set_icon_sensitive(gtk.ENTRY_ICON_SECONDARY,
            self.read_access)

    def get_access(self, type_):
        model = self.get_model()
        if model:
            return common.MODELACCESS[model][type_]
        else:
            return True

    @property
    def read_access(self):
        return self.get_access('read')

    @property
    def create_access(self):
        return self.attrs.get('create', True) and self.get_access('create')

    @property
    def modified(self):
        if self.record and self.field:
            value = self.wid_text.get_text()
            return self.field.get_client(self.record) != value
        return False

    def _color_widget(self):
        return self.wid_text

    @staticmethod
    def has_target(value):
        return value is not None

    @staticmethod
    def value_from_id(id_, str_=None):
        if str_ is None:
            str_ = ''
        return id_, str_

    @staticmethod
    def id_from_value(value):
        return value

    def sig_activate(self):
        model = self.get_model()
        if not model or not common.MODELACCESS[model]['read']:
            return
        if not self.focus_out or not self.field:
            return
        self.changed = False
        value = self.field.get(self.record)
        model = self.get_model()

        self.focus_out = False
        if model and not self.has_target(value):
            if (not self._readonly
                    and (self.wid_text.get_text()
                        or self.field.get_state_attrs(
                            self.record)['required'])):
                domain = self.field.domain_get(self.record)
                context = self.field.context_get(self.record)
                text = self.wid_text.get_text().decode('utf-8')

                def callback(result):
                    if result:
                        self.field.set_client(self.record,
                            self.value_from_id(*result[0]), force_change=True)
                    else:
                        self.wid_text.set_text('')
                    self.focus_out = True
                    self.changed = True

                win = WinSearch(model, callback, sel_multi=False,
                    context=context, domain=domain,
                    view_ids=self.attrs.get('view_ids', '').split(','),
                    views_preload=self.attrs.get('views', {}),
                    new=self.create_access)
                win.screen.search_filter(text)
                return
        self.focus_out = True
        self.changed = True
        return

    def get_screen(self):
        domain = self.field.domain_get(self.record)
        context = self.field.context_get(self.record)
        return Screen(self.get_model(), domain=domain, context=context,
            mode=['form'], view_ids=self.attrs.get('view_ids', '').split(','),
            views_preload=self.attrs.get('views', {}), readonly=self._readonly,
            exclude_field=self.attrs.get('relation_field'))

    def sig_new(self, *args):
        model = self.get_model()
        if not model or not common.MODELACCESS[model]['create']:
            return
        self.focus_out = False
        screen = self.get_screen()

        def callback(result):
            if result:
                self.field.set_client(self.record,
                    self.value_from_id(screen.current_record.id,
                        screen.current_record.rec_name()))
            self.focus_out = True
        WinForm(screen, callback, new=True, save_current=True)

    def sig_edit(self, *args):
        model = self.get_model()
        if not model or not common.MODELACCESS[model]['read']:
            return
        if not self.focus_out or not self.field:
            return
        self.changed = False
        value = self.field.get(self.record)
        model = self.get_model()

        self.focus_out = False
        if model and self.has_target(value):
            screen = self.get_screen()
            screen.load([self.id_from_value(self.field.get(self.record))])

            def callback(result):
                if result:
                    self.field.set_client(self.record,
                        self.value_from_id(screen.current_record.id,
                            screen.current_record.rec_name()),
                        force_change=True)
                self.focus_out = True
                self.changed = True
            WinForm(screen, callback, save_current=True)
            return
        elif model and not self._readonly:
            domain = self.field.domain_get(self.record)
            context = self.field.context_get(self.record)
            text = self.wid_text.get_text().decode('utf-8')

            def callback(result):
                if result:
                    self.field.set_client(self.record,
                        self.value_from_id(*result[0]), force_change=True)
                self.focus_out = True
                self.changed = True
            win = WinSearch(model, callback, sel_multi=False,
                context=context, domain=domain,
                view_ids=self.attrs.get('view_ids', '').split(','),
                views_preload=self.attrs.get('views', {}),
                new=self.create_access)
            win.screen.search_filter(text)
            return
        self.focus_out = True
        self.changed = True
        return

    def sig_key_press(self, widget, event, *args):
        editable = self.wid_text.get_editable()
        activate_keys = [gtk.keysyms.Tab, gtk.keysyms.ISO_Left_Tab]
        if not self.wid_completion:
            activate_keys.append(gtk.keysyms.Return)
        if (event.keyval == gtk.keysyms.F3
                and editable
                and self.create_access):
            self.sig_new(widget, event)
            return True
        elif event.keyval == gtk.keysyms.F2 and self.read_access:
            self.sig_edit(widget)
            return True
        elif (event.keyval in activate_keys
                and editable):
            self.sig_activate()
        elif (self.has_target(self.field.get(self.record))
                and editable
                and event.keyval in (gtk.keysyms.Delete,
                    gtk.keysyms.BackSpace)):
            self.wid_text.set_text('')
        return False

    def sig_changed(self, *args):
        if not self.changed:
            return False
        value = self.field.get(self.record)
        if self.has_target(value) and self.modified:
            def clean():
                if not self.wid_text.props.window:
                    return
                text = self.wid_text.get_text()
                position = self.wid_text.get_position()
                self.field.set_client(self.record,
                    self.value_from_id(None, ''))
                # The value of the field could be different of None
                # in such case, the original text should not be restored
                if not self.wid_text.get_text():
                    # Restore text and position after display
                    self.wid_text.set_text(text)
                    self.wid_text.set_position(position)
            gobject.idle_add(clean)
        return False

    def get_value(self):
        return self.wid_text.get_text()

    def set_value(self, record, field):
        if field.get_client(record) != self.wid_text.get_text():
            field.set_client(record, self.value_from_id(None, ''))
            self.wid_text.set_text('')

    def set_text(self, value):
        if not value:
            value = ''
        self.wid_text.set_text(value)
        self.wid_text.set_position(len(value))

    def display(self, record, field):
        self.changed = False
        super(Many2One, self).display(record, field)

        self._set_button_sensitive()

        if not field:
            self.wid_text.set_text('')
            self.wid_text.set_position(0)
            self.changed = True
            return False
        self.set_text(field.get_client(record))
        if self.has_target(field.get(record)):
            stock, tooltip = 'tryton-open', _('Open a record <F2>')
        else:
            stock, tooltip = 'tryton-find', _('Search a record <F2>')
        self.wid_text.set_icon_from_stock(gtk.ENTRY_ICON_SECONDARY, stock)
        self.wid_text.set_icon_tooltip_text(gtk.ENTRY_ICON_SECONDARY, tooltip)
        self.changed = True

    def _populate_popup(self, widget, menu):
        value = self.field.get(self.record)
        if self.has_target(value):
            # Delay filling of popup as it can take time
            gobject.idle_add(populate, menu, self.get_model(),
                self.id_from_value(value), '', self.field)
        return True

    def _completion_match_selected(self, completion, model, iter_):
        rec_name, record_id = model.get(iter_, 0, 1)
        self.field.set_client(self.record,
            self.value_from_id(record_id, rec_name), force_change=True)

        completion_model = self.wid_completion.get_model()
        completion_model.clear()
        completion_model.search_text = self.wid_text.get_text()
        return True

    def _update_completion(self, widget):
        if self._readonly:
            return
        if not self.record:
            return
        value = self.field.get(self.record)
        if self.has_target(value):
            id_ = self.id_from_value(value)
            if id_ is not None and id_ >= 0:
                return
        model = self.get_model()
        update_completion(self.wid_text, self.record, self.field, model)

    def _completion_action_activated(self, completion, index):
        if index == 0:
            self.sig_edit()
        elif index == 1:
            self.sig_new()
