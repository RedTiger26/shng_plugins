#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-     Thomas Ernst                       offline@gmx.net
#########################################################################
#  Finite state machine plugin for SmartHomeNG
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import re
from collections import OrderedDict
from . import StateEngineTools
try:
    import pydotplus
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False


# Class representing a value for a condition (either value or via item/eval)
class WebInterface(StateEngineTools.SeItemChild):
    # Constructor
    # abitem: parent SeItem instance

    @property
    def width(self):
        return self.__widthfactor

    @width.setter
    def width(self, value):
        self.__widthfactor = value

    @property
    def height(self):
        return self.__heightfactor

    @height.setter
    def height(self, value):
        self.__heightfactor = value

    def __init__(self, abitem):
        super().__init__(abitem)

        if not REQUIRED_PACKAGE_IMPORTED:
            self._log_warning("Unable to import Python package 'pydotplus'. Visualizing SE items will not work.")
        self.__img_path = abitem.se_plugin.path_join(abitem.se_plugin.get_plugin_dir(), 'webif/static/img/visualisations')
        self.__states = abitem.webif_infos
        self._abitem = abitem
        self.__name = abitem.id
        self.__active_conditionset = abitem.lastconditionset_name
        self.__active_state = abitem.laststate

        self.__graph = pydotplus.Dot('StateEngine', graph_type='digraph', splines='false',
                                     overlap='compress', compound='false', imagepath='{}'.format(self.__img_path))
        self.__graph.set_node_defaults(color='lightgray', style='filled', shape='box',
                                       fontname='Helvetica', fontsize='10', pin='true')
        self.__graph.set_edge_defaults(color='darkgray', style='filled', shape='box', labeldistance=2.5,
                                       fontname='Helvetica', fontsize='10', len=0.1)
        self.__graph.set_graph_defaults(sep=+0.15)
        self.__nodes = {}
        self.__heightfactor = 1
        self.__widthfactor = 1
        self.__textlimit = 105
        self.__conditionset_count = 0

    def __repr__(self):
        return "WebInterface item: {}, id {}".format(self.__states, self.__name) if REQUIRED_PACKAGE_IMPORTED else "None"

    def _strip_regex(self, regex_list):
        pattern_strings = []
        if not isinstance(regex_list, list):
            regex_list = [regex_list]
        for item in regex_list:
            if isinstance(item, re.Pattern):
                pattern_strings.append(item.pattern)
            else:
                pattern_match = re.search(r"re\.compile\('([^']*)'", item)
                if pattern_match:
                    item = f"regex:{pattern_match.group(1)}"
                pattern_strings.append(str(item))
        if len(pattern_strings) <= 1:
            pattern_strings = pattern_strings[0]
        return str(pattern_strings)

    def _actionlabel(self, state, label_type, conditionset, active):
        # Check if conditions for action are met or not
        # state: state where action is defined in
        # label_type: on_enter, on_stay, on_leave, on_pass
        # active: if action is currently run

        actionlabel = actionstart = '<<table border="0" cellpadding="2" cellborder="0">'
        action_tooltip = ''
        types = [label_type] if label_type in ['actions_leave', 'actions_pass'] else ['actions_enter_or_stay', label_type]
        tooltip_count = 0

        for label_type in types:
            for action in self.__states[state].get(label_type):
                action_dict = self.__states[state][label_type].get(action)
                if action_dict.get('actionstatus'):
                    _success = action_dict['actionstatus'].get('success')
                    _issue = action_dict['actionstatus'].get('issue')
                    _reason = action_dict['actionstatus'].get('reason')
                else:
                    _success = None
                    _issue = None
                    _reason = None
                _repeat = action_dict.get('repeat')
                _delay = int(float(action_dict.get('delay') or 0))

                cond1 = conditionset in ['', self.__active_conditionset] and state == self.__active_state
                cond2 = self.__states[state]['conditionsets'].get(conditionset) is not None

                fontcolor = "white" if (_success == "False" and active) and ((cond1 and cond2 and _reason) or (_reason and label_type in ['actions_leave', 'actions_pass'])) \
                    else "#f4c430" if _delay > 0 and active else "darkred" if _delay < 0 and active \
                    else "#303030" if _issue else "black"

                if _issue:
                    if tooltip_count > 0:
                        action_tooltip += '&#13;&#10;&#13;&#10;'
                    tooltip_count += 1
                    action_tooltip += '{}'.format(_issue) if _issue is not None else ''

                additionaltext = " (issue: see tooltip)" if _issue is not None \
                    else _reason if _reason is not None \
                    else " (delay: {})".format(_delay) if _delay > 0\
                    else " (cancel delay!)" if _delay == -1 \
                    else " (wrong delay!)" if _delay < -1 \
                    else ""
                action1 = action_dict.get('function')
                if action1 in ['set', 'force set']:
                    action2 = str(action_dict.get('item'))
                    value_check = str(action_dict.get('value'))
                    value_check = '""' if value_check == "" else value_check
                    is_number = value_check.lstrip('-').replace('.', '', 1).isdigit()
                    if is_number and "." in value_check:
                        value_check = round(float(value_check), 2)
                    action3 = 'to {}'.format(value_check)
                elif action1 == 'special':
                    action2 = str(action_dict.get('special'))
                    action3 = str(action_dict.get('value'))
                else:
                    action2 = 'None'
                    action3 = ""
                success_info = '<td width="26"><img src="sign_warn.png" /></td></tr>' \
                    if _issue is not None and active \
                    else '<td width="26"><img src="sign_false.png" /></td></tr>' \
                    if _success == 'False' and active \
                    else '<td width="26"><img src="sign_scheduled.png" /></td></tr>' \
                    if _success == 'Scheduled' and active \
                    else '<td width="26"><img src="sign_delay.png" /></td></tr>' \
                    if _success == 'True' and active and _delay > 0 \
                    else '<td width="26"><img src="sign_true.png" /></td></tr>' \
                    if _success == 'True' and active \
                    else '<td width="10"></td></tr>'
                if not action2 == 'None':
                    actionlabel += '<tr class="actionentry"><td align="center"><font color="{}">{} {} {} {}</font></td>'.format(fontcolor, action1, action2, action3, additionaltext)
                    actionlabel += '{}'.format(success_info)

        actionlabel += '</table>>'
        actionend = '</table>>'
        actionlabel = '' if actionlabel == '{}{}'.format(actionstart, actionend)\
                      or actionlabel == '<>' else actionlabel
        #self._log_debug('actionlabel: {}', actionlabel)
        return actionlabel, action_tooltip, tooltip_count

    def _conditionlabel(self, state, conditionset):
        condition_tooltip = ''
        conditions_done = []
        _empty_set = self.__states[state]['conditionsets'].get(conditionset) == ''
        if _empty_set:
            return '', '', 0
        conditionlist = '<<table border="0" cellpadding="5" cellborder="0">'
        conditionlist += '<tr class="conditionset"><td align="center" colspan="4" bgcolor="white">{}</td></tr>'.format(conditionset)
        tooltip_count = 0
        for k, condition in enumerate(self.__states[state]['conditionsets'].get(conditionset)):
            condition_dict = self.__states[state]['conditionsets'][conditionset].get(condition)
            current = condition_dict.get('current')
            match = condition_dict.get('match')
            status_none = str(condition_dict.get('status')) == 'None'
            item_none = str(condition_dict.get('item')) == 'None' or not status_none
            status_eval_none = condition_dict.get('status_eval') == 'None'
            eval_none = condition_dict.get('eval') == 'None' or not status_eval_none
            value_none = str(condition_dict.get('value')) == 'None'
            min_none = condition_dict.get('min') == 'None'
            max_none = condition_dict.get('max') == 'None'
            agemin_none = condition_dict.get('agemin') == 'None'
            agemax_none = condition_dict.get('agemax') == 'None'
            changedby_none = condition_dict.get('changedby') == 'None'
            updatedby_none = condition_dict.get('updatedby') == 'None'
            triggeredby_none = condition_dict.get('triggeredby') == 'None'

            for compare in condition_dict:
                cond1 = not condition_dict.get(compare) == 'None'
                excluded_values = ['item', 'eval', 'negate', 'agenegate', 'changedbynegate',
                                   'updatedbynegate', 'triggeredbynegate', 'status', 'current', 'match', 'status_eval']

                if cond1 and compare not in excluded_values:
                    if condition not in conditions_done:
                        current_clean = ", ".join(f"{k} = {v}" for k, v in current.items())
                        text = " Current {}".format(current_clean) if current is not None and len(current) > 0 else " Not evaluated."
                        conditionlist += ('<tr class="conditionheader"><td align="center" colspan="2"><table border="0" cellpadding="0" '
                                          'cellborder="0"><tr><td></td><td align="center">{}:{}</td>'
                                          '<td></td></tr><tr class="conditionline">'
                                          '<td width="40%"></td><td align="center" border="1" height="1"></td>'
                                          '<td width="40%"></td></tr></table></td></tr>').format(condition.upper(), text)
                    conditions_done.append(condition)
                    conditionlist += '<tr class="conditionentry"><td align="center"><b>'
                    info_status = str(condition_dict.get('status') or 'n/a')
                    info_item = str(condition_dict.get('item') or 'n/a')
                    info_eval = str(condition_dict.get('eval') or 'n/a')
                    info_status_eval = str(condition_dict.get('status_eval') or 'n/a')
                    info_compare = str(condition_dict.get(compare) or '')
                    info_compare = self._strip_regex(info_compare)
                    if not status_none:
                        textlength = len(info_status)
                        if textlength > self.__textlimit:
                            if tooltip_count > 0:
                                condition_tooltip += '&#13;&#10;&#13;&#10;'
                            tooltip_count += 1
                            condition_tooltip += '{}'.format(condition_dict.get('status'))
                    elif not status_eval_none:
                        textlength = len(info_status_eval)
                        if textlength > self.__textlimit:
                            if tooltip_count > 0:
                                condition_tooltip += '&#13;&#10;&#13;&#10;'
                            tooltip_count += 1
                            condition_tooltip += '{}'.format(condition_dict.get('status_eval'))
                    elif not eval_none:
                        textlength = len(info_eval)
                        if textlength > self.__textlimit:
                            if tooltip_count > 0:
                                condition_tooltip += '&#13;&#10;&#13;&#10;'
                            tooltip_count += 1
                            condition_tooltip += '{}'.format(condition_dict.get('eval'))
                    elif not item_none:
                        textlength = len(info_item)
                        if textlength > self.__textlimit:
                            if tooltip_count > 0:
                                condition_tooltip += '&#13;&#10;&#13;&#10;'
                            tooltip_count += 1
                            condition_tooltip += '{}'.format(condition_dict.get('item'))
                    else:
                        textlength = 0

                    info_item = info_item[:self.__textlimit] + '.. &nbsp;' * int(textlength > self.__textlimit)
                    info_status = info_status[:self.__textlimit] + '.. &nbsp;' * int(textlength > self.__textlimit)
                    info_eval = info_eval[:self.__textlimit] + '.. &nbsp;' * int(textlength > self.__textlimit)
                    info_status_eval = info_status_eval[:self.__textlimit] + '.. &nbsp;' * int(textlength > self.__textlimit)
                    info_value = info_compare[:self.__textlimit] + '.. &nbsp;' * int(len(info_compare) > self.__textlimit)
                    textlength = len(info_compare)
                    if textlength > self.__textlimit:
                        if tooltip_count > 0:
                            condition_tooltip += '&#13;&#10;&#13;&#10;'
                        tooltip_count += 1
                        condition_tooltip += '{}'.format(condition_dict.get(compare))

                    if not status_none:
                        info = info_status
                    elif not status_eval_none:
                        info = info_status_eval
                    elif not eval_none:
                        info = info_eval
                    elif not item_none:
                        info = info_item
                    else:
                        info = "n/a"

                    conditionlist += '{}</b>'.format(info)
                    comparison = "&#62;=" if not min_none and compare == "min"\
                                 else "&#60;=" if not max_none and compare == "max"\
                                 else "older" if not agemin_none and compare == "agemin"\
                                 else "younger" if not agemax_none and compare == "agemax"\
                                 else "not changed by" if (not changedby_none and compare == "changedby"
                                                           and condition_dict.get('changedbynegate') == 'True')\
                                 else "changed by" if not changedby_none and compare == "changedby"\
                                 else "not updated by" if (not updatedby_none and compare == "updatedby"
                                                           and condition_dict.get('updatedbynegate') == 'True')\
                                 else "updated by" if not updatedby_none and compare == "updatedby"\
                                 else "not triggered by" if (not triggeredby_none and compare == "triggeredby"
                                                             and condition_dict.get('triggeredbynegate') == 'True')\
                                 else "triggered by" if not triggeredby_none and compare == "triggeredby"\
                                 else "!=" if (not value_none and compare == "value"
                                               and condition_dict.get('negate') == 'True')\
                                 else "=="

                    match_info = ''
                    if match and len(match) > 0:
                        match_info = match.get('value') if compare in ["min", "max", "value"]\
                                     else match.get('age') if compare in ["agemin", "agemax", "age"]\
                                     else match.get(compare)
                    conditionlist += '&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;{}&nbsp;&nbsp;&nbsp;'.format(comparison)
                    conditionlist += '"{}"'.format(info) if not item_none and not status_none \
                        and not eval_none and not status_eval_none else ''

                    info = info_value
                    cond1 = eval_none and not item_none
                    cond2 = eval_none and (not status_none or not status_eval_none)
                    cond3 = not eval_none and item_none
                    cond4 = not eval_none and status_eval_none and status_none
                    conditionlist += '{}'.format(info) if not condition_dict.get(compare) == 'None' and (
                                     cond1 or cond2 or cond3 or cond4) else ''
                    conditionlist += ' (negate)' if condition_dict.get('negate') == 'True' and "age" \
                                     not in compare and not compare == "value" else ''
                    conditionlist += ' (negate)' if condition_dict.get('agenegate') == 'True' and "age" in compare else ''
                    match_info = '<img src="sign_true.png" />' if match_info == 'yes'\
                                 else '<img src="sign_false.png" />' if match_info == 'no'\
                                 else '<img src="sign_warn.png" />' if match_info and len(match_info) > 0 \
                                 else '<img src="sign_empty.png" />'
                    conditionlist += '</td><td>{}</td></tr>'.format(match_info)
        conditionlist += '<tr><td></td><td></td></tr></table>>'
        return conditionlist, condition_tooltip, tooltip_count

    def _add_actioncondition(self, state, conditionset, action_type, new_y, cond1, cond2):
        cond4 = conditionset in ['', self.__active_conditionset] and state == self.__active_state
        cond5 = self.__states[state]['conditionsets'].get(conditionset) is not None
        cond_enter = action_type in ['actions_enter', 'actions_enter_or_stay'] and self.__states[state].get('enter') is False
        cond_stay = action_type in ['actions_stay', 'actions_enter_or_stay'] and self.__states[state].get('stay') is False
        color_enter = "gray" if (cond1 and cond2 and cond5) or \
                                (cond_enter and cond4 and cond5) else "olivedrab" if cond4 else "indianred2"
        color_stay = "gray" if (cond1 and cond2 and cond5) or \
                               (cond_stay and cond4 and cond5) else "olivedrab" if cond4 else "indianred2"

        label = 'first enter' if action_type in ['actions_enter', 'actions_enter_or_stay'] else 'staying'

        position = '{},{}!'.format(12.6 * self.__widthfactor, new_y)
        color = color_enter if label == 'first enter' else color_stay
        self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)] = \
            pydotplus.Node('{}_{}_state_{}'.format(state, conditionset, action_type), style="filled", fillcolor=color,
                           shape="diamond", label=label, pos=position)
        self.__graph.add_node(self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)])
        if self.__nodes.get('{}_{}_state_actions_enter_edge'.format(state, conditionset)) is None:
            self.__nodes['{}_{}_state_{}_edge'.format(state, conditionset, action_type)] = \
                pydotplus.Edge(self.__nodes['{}_{}'.format(state, conditionset)], self.__nodes['{}_{}_state_{}'.format(
                    state, conditionset, action_type)], style='bold', taillabel="True",  tooltip='first enter')
            self.__graph.add_edge(self.__nodes['{}_{}_state_{}_edge'.format(state, conditionset, action_type)])
        else:
            self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}_state_actions_enter'.format(state, conditionset)],
                                                 self.__nodes['{}_{}_state_actions_stay'.format(state, conditionset)],
                                                 style='bold', label="False    "))
        self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}_state_{}'.format(state, conditionset, action_type)],
                                             self.__nodes['{}_{}_{}'.format(state, conditionset, action_type)],
                                             style='bold', taillabel="True"))
        try:
            if action_type == 'actions_enter':
                self.__nodes['{}_{}_actions_enter'.format(state, conditionset)].obj_dict['attributes']['fillcolor'] = color
        except Exception:
            pass
        try:
            if action_type == 'actions_stay':
                self.__nodes['{}_{}_actions_stay'.format(state, conditionset)].obj_dict['attributes']['fillcolor'] = color
        except Exception:
            pass

    def drawgraph(self, filename):
        new_y = 0
        previous_state = ''
        previous_conditionset = ''
        above_nodeheights = []
        last_action_nodeheight = 0
        for i, state in enumerate(self.__states):
            #self._log_debug('Adding state for webif {}', self.__states[state])
            if not isinstance(self.__states[state], (OrderedDict, dict)):
                continue
            self.__conditionset_count = len(self.__states[state].get('conditionsets'))
            if self.__conditionset_count == 0:
                self.__states[state]['conditionsets'][''] = ''
            try:
                list_index = list(self.__states.keys()).index(self.__active_state)
            except Exception:
                list_index = 0
            color = "olivedrab" if state == self.__active_state \
                else "gray" if i > list_index else "indianred2"

            if not i == 0:
                new_y -= max(float(above_nodeheights[-1] + 0.3), 0.46, float(last_action_nodeheight)) * self.__heightfactor # half elipse added at end
                position = '{},{}!'.format(0, new_y)

                condition_node = 'pass' if self.__nodes.get('{}_pass'.format(previous_state)) \
                        else 'leave' if self.__nodes.get('{}_leave'.format(previous_state)) \
                        else list(self.__states[previous_state]['conditionsets'].keys())[-1]
                lastnode = self.__nodes['{}_{}'.format(previous_state, condition_node)]
                self.__nodes['{}_above'.format(state)] = pydotplus.Node('{}_above'.format(state), pos=position,
                                                                        shape="square", width="0", label="")
                self.__graph.add_node(self.__nodes['{}_above'.format(state)])
                position = '{},{}!'.format(10 * self.__widthfactor, new_y)
                self.__nodes['{}_above_right'.format(state)] = pydotplus.Node('{}_above_right'.format(state),
                                                                              pos=position, shape="square", width="0", label="")
                self.__graph.add_node(self.__nodes['{}_above_right'.format(state)])
                self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_above'.format(state)],
                                                     self.__nodes['{}_above_right'.format(state)], style='bold',
                                                     color='black', label="", dir="none"))
                self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_above_right'.format(state)], lastnode,
                                                     style='bold', color='black', label="False   ", dir="none"))
                self.__graph.add_edge(pydotplus.Edge(state, self.__nodes['{}_above'.format(state)], style='bold',
                                                     color='black', label="", dir="back"))
            new_y -= 1.5 * self.__heightfactor
            position = '{},{}!'.format(0, new_y)
            #self._log_debug('state: {} {}',state, position)

            self.__nodes[state] = pydotplus.Node(state, pos=position, pin=True, notranslate=True, style="filled",
                                                 fillcolor=color, shape="ellipse",
                                                 label='<<table border="0"><tr><td>{}</td></tr><hr/><tr>'
                                                       '<td>{}</td></tr></table>>'.format(
                                                        state, self.__states[state]['name']))
            position = '{},{}!'.format(10 * self.__widthfactor, new_y)
            self.__nodes['{}_right'.format(state)] = pydotplus.Node('{}_right'.format(state), pos=position,
                                                                    shape="square", width="0", label="")
            self.__graph.add_node(self.__nodes[state])
            self.__graph.add_node(self.__nodes['{}_right'.format(state)])
            conditionset_nodeheights = []
            actionlist_enter = ''
            actionlist_stay = ''
            actionlist_leave = ''
            actionlist_pass = ''
            condition_tooltip = ''
            action_tooltip = ''
            j = 0
            new_x = 0.55
            actions_enter = self.__states[state].get('actions_enter') or []
            actions_enter_or_stay = self.__states[state].get('actions_enter_or_stay') or []
            actions_stay = self.__states[state].get('actions_stay') or []
            actions_leave = self.__states[state].get('actions_leave') or []
            actions_pass = self.__states[state].get('actions_pass') or []
            action_tooltip_count_enter = 0
            action_tooltip_count_stay = 0
            action_tooltip_count_leave = 0
            action_tooltip_count_pass = 0
            action_tooltip_enter = ""
            action_tooltip_stay = ""
            action_tooltip_leave = ""
            action_tooltip_pass = ""
            action_y = new_y
            actions_nodeheights = {}
            nodeheight = 0

            for j, conditionset in enumerate(self.__states[state]['conditionsets']):
                cond3 = conditionset == ''
                try:
                    cond1 = i >= list(self.__states.keys()).index(self.__active_state)
                except Exception:
                    cond1 = True
                try:
                    cond4 = i == list(self.__states.keys()).index(self.__active_state)
                except Exception:
                    cond4 = True
                #self._log_debug('i {}, index of active state {}', i, list(self.__states.keys()).index(self.__active_state))
                try:
                    cond2 = (j > list(self.__states[state]['conditionsets'].keys()).index(self.__active_conditionset)
                             or i > list(self.__states.keys()).index(self.__active_state))
                except Exception:
                    cond2 = False if cond3 and cond4 else True
                color = "gray" if cond1 and cond2 else "olivedrab" \
                    if (conditionset == self.__active_conditionset or cond3) and state == self.__active_state else "indianred2"
                try:
                    cond5 = i >= list(self.__states.keys()).index(self.__active_state)
                except Exception:
                    cond5 = True

                cond6 = conditionset in ['', self.__active_conditionset] and state == self.__active_state
                cond_enter = True if self.__states[state].get('enter') is True else False
                cond_stay = True if self.__states[state].get('stay') is True else False
                active = True if cond_enter and cond6 else False

                if len(actions_enter) > 0 or len(actions_enter_or_stay) > 0:
                    actionlist_enter, action_tooltip_enter, action_tooltip_count_enter = \
                        self._actionlabel(state, 'actions_enter', conditionset, active)
                active = True if cond_stay and cond6 else False
                if len(actions_stay) > 0 or len(actions_enter_or_stay) > 0:
                    actionlist_stay, action_tooltip_stay, action_tooltip_count_stay = \
                        self._actionlabel(state, 'actions_stay', conditionset, active)
                cond_leave = True if self.__states[state].get('leave') is True else False
                active = True if cond_leave else False

                if len(actions_leave) > 0:
                    actionlist_leave, action_tooltip_leave, action_tooltip_count_leave = \
                        self._actionlabel(state, 'actions_leave', conditionset, active)
                cond_pass = True if self.__states[state].get('pass') is True else False
                active = False if (cond5 and not cond_pass) or cond_leave else True
                if len(actions_pass) > 0:
                    actionlist_pass, action_tooltip_pass, action_tooltip_count_pass = \
                        self._actionlabel(state, 'actions_pass', conditionset, active)

                conditionlist, condition_tooltip, condition_tooltip_count = self._conditionlabel(state, conditionset)
                titles = len(re.findall(r'<tr class="conditionheader">', conditionlist))
                entries = len(re.findall(r'<tr class="conditionentry">', conditionlist))
                nodeheight = 0.958 + 0.5 + 0.479 # main header, last line, spacing on top and bottom
                nodeheight += titles * 1.292 # each title
                nodeheight += entries * 1 #each entry
                nodeheight /= 5.7
                nodeheight = round(nodeheight, 4)
                conditionset_nodeheights.append(nodeheight)
                new_y -= nodeheight * self.__heightfactor
                if j > 0:
                    new_y -= max(float(actions_nodeheights.get(j-1, 0.0) + 0.2), conditionset_nodeheights[j-1] + 0.2) * self.__heightfactor
                else:
                    new_y -= 0.46 * self.__heightfactor # half ellipse on top
                position = '{},{}!'.format(10 * self.__widthfactor, new_y)
                label = 'no condition' if conditionset == '' else conditionset
                self.__nodes['{}_{}'.format(state, conditionset)] = pydotplus.Node(
                    '{}_{}'.format(state, conditionset), style="filled", fillcolor=color, shape="diamond",
                    label=label, pos=position)
                #self._log_debug('Node {} {} drawn. Conditionlist {}', state, conditionset, conditionlist)
                position = '{},{}!'.format(3 * self.__widthfactor, new_y)
                xlabel = '1 tooltip' if condition_tooltip_count == 1\
                         else '{} tooltips'.format(condition_tooltip_count)\
                         if condition_tooltip_count > 1 else ''
                if not conditionlist == '':
                    self.__nodes['{}_{}_conditions'.format(state, conditionset)] = pydotplus.Node(
                        '{}_{}_conditions'.format(state, conditionset), style="filled", fillcolor=color,
                        shape="rect", label=conditionlist, pos=position, tooltip=condition_tooltip, xlabel=xlabel)
                    self.__graph.add_node(self.__nodes['{}_{}_conditions'.format(state, conditionset)])
                    # Create a dotted line between conditionlist and conditionset name
                    parenthesis_edge = pydotplus.Edge(self.__nodes['{}_{}_conditions'.format(state, conditionset)],
                                                      self.__nodes['{}_{}'.format(state, conditionset)],
                                                      arrowhead="none", color="black", style="dotted", constraint="false")
                    self.__graph.add_edge(parenthesis_edge)
                self.__graph.add_node(self.__nodes['{}_{}'.format(state, conditionset)])
                action_y = new_y
                new_x = 17.5 * self.__widthfactor
                nodeheights = 0
                nodeheight = 0

                if not actionlist_enter == '':
                    nodeheight = 0.644
                    nodeheight += len(re.findall(r'<tr class="actionentry">', actionlist_enter)) * 0.67
                    nodeheight /= 5.7
                    nodeheight = round(nodeheight, 4)
                    nodeheight = max(0.4, nodeheight)
                    nodeheights += nodeheight
                    last_action_nodeheight = nodeheight
                    position = '{},{}!'.format(new_x, action_y)
                    xlabel = '1 tooltip' if action_tooltip_count_enter == 1\
                             else '{} tooltips'.format(action_tooltip_count_enter)\
                             if action_tooltip_count_enter > 1 else ''
                    #self._log_debug('action enter: {}', position)
                    self.__nodes['{}_{}_actions_enter'.format(state, conditionset)] = pydotplus.Node(
                        '{}_{}_actions_enter'.format(state, conditionset), style="filled", fillcolor=color,
                        shape="rectangle", label=actionlist_enter, pos=position, tooltip=action_tooltip_enter,
                        xlabel=xlabel)
                    self.__graph.add_node(self.__nodes['{}_{}_actions_enter'.format(state, conditionset)])
                    self._add_actioncondition(state, conditionset, 'actions_enter', action_y, cond1, cond2)

                if not actionlist_stay == '':
                    add_nodeheight = nodeheight
                    action_y -= nodeheight * self.__heightfactor
                    nodeheight = 0.644
                    nodeheight += len(re.findall(r'<tr class="actionentry">', actionlist_stay)) * 0.67
                    nodeheight /= 5.7
                    nodeheight = round(nodeheight, 4)
                    nodeheight = max(0.4, nodeheight)
                    add_nodeheight += nodeheight
                    if action_y != new_y:
                        nodeheight += 0.2
                        action_y -= nodeheight * self.__heightfactor
                    elif j <= len(self.__states[state]['conditionsets']) - 1:
                        add_nodeheight = 0
                    nodeheights += nodeheight * 2 - 0.2
                    last_action_nodeheight = nodeheight + add_nodeheight

                    position = '{},{}!'.format(new_x, action_y)

                    xlabel = '1 tooltip' if action_tooltip_count_stay == 1\
                             else '{} tooltips'.format(action_tooltip_count_stay)\
                             if action_tooltip_count_stay > 1 else ''
                    #self._log_debug('action stay: {}', position)
                    self.__nodes['{}_{}_actions_stay'.format(state, conditionset)] = pydotplus.Node(
                        '{}_{}_actions_stay'.format(state, conditionset), style="filled", fillcolor=color,
                        shape="rectangle", label=actionlist_stay, pos=position, tooltip=action_tooltip_stay,
                        xlabel=xlabel)
                    self.__graph.add_node(self.__nodes['{}_{}_actions_stay'.format(state, conditionset)])
                    self._add_actioncondition(state, conditionset, 'actions_stay', action_y, cond1, cond2)

                actions_nodeheights[j] = nodeheights
                position = '{},{}!'.format(17.5 * self.__widthfactor, action_y)
                cond1 = self.__nodes.get('{}_{}_actions_enter'.format(state, conditionset)) is None
                cond2 = self.__nodes.get('{}_{}_actions_stay'.format(state, conditionset)) is None
                cond3 = self.__nodes.get('{}_{}_actions_leave'.format(state, conditionset)) is None
                cond4 = self.__nodes.get('{}_{}_actions_pass'.format(state, conditionset)) is None
                if cond1 and cond2 and cond3 and cond4:
                    actions_nodeheights[j] = 0.5
                    last_action_nodeheight = 0.5
                    nodeheight= 0.5
                    self.__nodes['{}_{}_right'.format(state, conditionset)] = pydotplus.Node('{}_{}_right'.format(
                        state, conditionset), shape="circle", width="0.7", pos=position, label="", fillcolor="black",
                        style="filled", tooltip="No Action")
                    self.__graph.add_node(self.__nodes['{}_{}_right'.format(state, conditionset)])
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_{}'.format(state, conditionset)],
                                                         self.__nodes['{}_{}_right'.format(state, conditionset)],
                                                         style='bold', taillabel="True", tooltip='action on enter'))
                if self.__states[state].get('is_copy_for'):
                    xlabel = "can currently release {}\n\r".format(self.__states[state].get('is_copy_for'))
                elif self.__states[state].get('releasedby'):
                    xlabel = "can currently get released by {}\n\r".format(self.__states[state].get('releasedby'))
                else:
                    xlabel = ""
                if j == 0:
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes[state], self.__nodes['{}_right'.format(state)],
                                                         style='bold', color='black', dir='none',
                                                         xlabel=xlabel, edgetooltip='check first conditionset'))
                    self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_right'.format(state)],
                                                         self.__nodes['{}_{}'.format(state, conditionset)],
                                                         style='bold', color='black', tooltip='check first conditionset'))
                    #self._log_debug('Drew line from state')
                else:
                    self.__graph.add_edge(pydotplus.Edge(previous_conditionset,
                                                         self.__nodes['{}_{}'.format(state, conditionset)],
                                                         style='bold', color='black', tooltip='check next conditionset'))
                previous_conditionset = self.__nodes['{}_{}'.format(state, conditionset)]

            end_node_heights = 0
            if len(actions_leave) > 0:
                action_y -= nodeheight * self.__heightfactor
                nodeheight = 0.8
                nodeheight += len(re.findall(r'<tr class="actionentry">', actionlist_leave)) * 0.67
                nodeheight /= 5.7
                nodeheight = round(nodeheight, 4)
                end_node_heights += max(0.5, nodeheight) + last_action_nodeheight
                last_action_nodeheight = max(1.0, nodeheight)
                action_y -= max(0.5, nodeheight) * self.__heightfactor
                new_y = action_y
                position = '{},{}!'.format(10 * self.__widthfactor, action_y)
                try:
                    cond2 = i >= list(self.__states.keys()).index(self.__active_state)
                except Exception:
                    cond2 = True
                cond3 = True if self.__states[state].get('leave') is True else False
                color = "gray" if cond2 and not cond3 else "olivedrab" if cond3 else "indianred2"
                self.__nodes['{}_leave'.format(state)] = pydotplus.Node('{}_leave'.format(state),
                                                                        style="filled", fillcolor=color, shape="diamond",
                                                                        label='leave', pos=position)
                self.__graph.add_node(self.__nodes['{}_leave'.format(state)])
                self.__graph.add_edge(pydotplus.Edge(previous_conditionset, self.__nodes['{}_leave'.format(state)],
                                                     style='bold', color='black', tooltip='check leave'))

                position = '{},{}!'.format(new_x, action_y)
                xlabel = '1 tooltip' if action_tooltip_count_leave == 1\
                         else '{} tooltips'.format(action_tooltip_count_leave)\
                         if action_tooltip_count_leave > 1 else ''
                #self._log_debug('action leave: {}', position)
                self.__nodes['{}_actions_leave'.format(state)] = pydotplus.Node('{}_actions_leave'.format(state),
                                                                                style="filled", fillcolor=color,
                                                                                shape="rectangle", label=actionlist_leave,
                                                                                pos=position, align="center",
                                                                                tooltip=action_tooltip_leave,
                                                                                xlabel=xlabel)
                self.__graph.add_node(self.__nodes['{}_actions_leave'.format(state)])
                self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_leave'.format(state)],
                                                     self.__nodes['{}_actions_leave'.format(state)], style='bold',
                                                     taillabel="True",  tooltip='run leave actions'))
                previous_conditionset = self.__nodes['{}_leave'.format(state)]
                nodeheight += 0.2

            if len(actions_pass) > 0:
                action_y -= nodeheight * self.__heightfactor
                nodeheight = 0.8
                nodeheight += len(re.findall(r'<tr class="actionentry">', actionlist_pass)) * 0.67
                nodeheight /= 5.7
                nodeheight = round(nodeheight, 4)
                if end_node_heights == 0:
                    end_node_heights += last_action_nodeheight
                last_action_nodeheight = max(1.0, nodeheight)
                end_node_heights += max(0.5, nodeheight)
                action_y -= max(0.5, nodeheight) * self.__heightfactor
                new_y = action_y
                position = '{},{}!'.format(10 * self.__widthfactor, action_y)
                try:
                    cond2 = i >= list(self.__states.keys()).index(self.__active_state)
                except Exception:
                    cond2 = True
                cond3 = True if self.__states[state].get('pass') is True else False
                color = "gray" if cond2 and not cond3 else "olivedrab" if cond3 else "indianred2"
                self.__nodes['{}_pass'.format(state)] = pydotplus.Node('{}_pass'.format(state),
                                                                       style="filled", fillcolor=color, shape="diamond",
                                                                       label='pass', pos=position)
                self.__graph.add_node(self.__nodes['{}_pass'.format(state)])
                self.__graph.add_edge(pydotplus.Edge(previous_conditionset, self.__nodes['{}_pass'.format(state)],
                                                     style='bold', color='black', tooltip='check pass'))

                position = '{},{}!'.format(new_x, action_y)
                xlabel = '1 tooltip' if action_tooltip_count_pass == 1\
                         else '{} tooltips'.format(action_tooltip_count_pass)\
                         if action_tooltip_count_pass > 1 else ''
                #self._log_debug('action pass: {}', position)
                self.__nodes['{}_actions_pass'.format(state)] = pydotplus.Node('{}_actions_pass'.format(state),
                                                                               style="filled", fillcolor=color,
                                                                               shape="rectangle", label=actionlist_pass,
                                                                               pos=position, align="center",
                                                                               tooltip=action_tooltip_pass,
                                                                               xlabel=xlabel)
                self.__graph.add_node(self.__nodes['{}_actions_pass'.format(state)])
                self.__graph.add_edge(pydotplus.Edge(self.__nodes['{}_pass'.format(state)],
                                                     self.__nodes['{}_actions_pass'.format(state)], style='bold',
                                                     taillabel="    True",  tooltip='run pass actions'))
            last_height = conditionset_nodeheights[-1] - end_node_heights + 0.1
            conditionset_nodeheights.append(last_height)
            above_nodeheights = conditionset_nodeheights
            previous_state = state

        result = self.__graph.write_svg(filename, prog='neato')
        return result
