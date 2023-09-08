#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2018 Thomas Ernst                       offline@gmx.net
#  Copyright 2019- Onkel Andy                       onkelandy@hotmail.com
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
import logging
import threading
import re
from . import StateEngineLogger
from . import StateEngineTools
from lib.item import Items


class SeFunctions:
    # return instance of smarthome.py class
    @property
    def ab_alive(self):
        return self.__ab_alive

    @ab_alive.setter
    def ab_alive(self, value):
        self.__ab_alive = value

    def __init__(self, smarthome=None, logger=None):
        self.logger = logger
        self.__sh = smarthome
        self.__locks = {}
        self.__global_struct = {}
        self.__ab_alive = False
        self.itemsApi = Items.get_instance()

    def __repr__(self):
        return "SeFunctions"

    # get a lock object
    # lock_id: Id of the lock object to return
    def __get_lock(self, lock_id):
        if lock_id not in self.__locks:
            self.__locks[lock_id] = threading.Lock()
        return self.__locks[lock_id]

    # return new item value for "manual" item
    # item_id: Id of "manual" item
    # caller: Caller that triggered the update
    # source: Source that triggered the update
    # The Method will determine the original caller/source and then check if this original caller/source is not
    # contained in se_manual_exclude list (if given) and is contained in se_manual_include list (if given).
    # If the original caller/source should be considered, the method returns the inverted value of the item.
    # Otherwise, the method returns the current value of the item, so that no change will be made
    def manual_item_update_eval(self, item_id, caller=None, source=None):
        item = self.itemsApi.return_item(item_id)
        if item is None:
            self.logger.error("manual_item_update_eval: item {0} not found!".format(item_id))

        # Leave immediately in case StateEngine Plugin is not yet fully running
        if not self.__ab_alive:
            return item()

        lock = self.__get_lock(item_id)
        try:
            lock.acquire()

            if "se_manual_logitem" in item.conf:
                elog_item_id = item.conf["se_manual_logitem"]
                elog_item = self.itemsApi.return_item(elog_item_id)
                if elog_item is None:
                    self.logger.error("manual_item_update_item: se_manual_logitem {0} not found!".format(elog_item_id))
                    elog = StateEngineLogger.SeLoggerDummy()
                else:
                    elog = StateEngineLogger.SeLogger.create(elog_item, manual=True)
            else:
                elog = StateEngineLogger.SeLoggerDummy()
            elog.header("manual_item_update_eval")
            elog.info("running for item '{0}' source '{1}' caller '{2}'", item_id, caller, source)

            retval_no_trigger = item()
            retval_trigger = not item()
            elog.info("Current value of item {0} is {1}", item_id, retval_no_trigger)

            original_caller, original_source = StateEngineTools.get_original_caller(elog, caller, source)
            elog.info("get_caller({0}, {1}): original trigger by {2}:{3}", caller, source,
                      original_caller, original_source)
            original = "{}:{}".format(original_caller, original_source)
            entry = re.compile("Stateengine Plugin", re.IGNORECASE)
            result = entry.match(original)
            if result is not None:
                elog.info("Manual item updated by Stateengine Plugin. Ignoring change and writing value {}",
                          retval_no_trigger)
                return retval_no_trigger

            if "se_manual_on" in item.conf:
                # get list of include entries
                include = item.conf["se_manual_on"]
                if isinstance(include, str):
                    include = [include, ]
                elif not isinstance(include, list):
                    elog.error("Item '{0}', Attribute 'se_manual_on': Value must be a string or a list!", item_id)
                    return retval_no_trigger
                elog.info("checking manual on values: {0}", include)
                elog.increase_indent()

                # If current value is in list -> Return "Trigger"
                for entry in include:
                    entry = re.compile(entry, re.IGNORECASE)
                    result = entry.match(original)
                    elog.info("Checking regex result {}", result)
                    if result is not None:
                        elog.info("{0}: matching. Writing value {1}", entry, retval_no_trigger)
                        return retval_no_trigger
                    elog.info("{0}: not matching", entry)
                elog.decrease_indent()

            if "se_manual_exclude" in item.conf:
                # get list of exclude entries
                exclude = item.conf["se_manual_exclude"]

                if isinstance(exclude, str):
                    exclude = [exclude, ]
                elif not isinstance(exclude, list):
                    elog.error("Item '{0}', Attribute 'se_manual_exclude': Value must be a string or a list!", item_id)
                    return retval_no_trigger
                elog.info("checking exclude values: {0}", exclude)
                elog.increase_indent()

                # If current value is in list -> Return "NoTrigger"
                for entry in exclude:
                    entry = re.compile(entry, re.IGNORECASE)
                    result = entry.match(original)
                    elog.info("Checking regex result {}", result)
                    if result is not None:
                        elog.info("{0}: matching. Writing value {1}", entry, retval_no_trigger)
                        return retval_no_trigger
                    elog.info("{0}: not matching", entry)
                elog.decrease_indent()

            if "se_manual_include" in item.conf:
                # get list of include entries
                include = item.conf["se_manual_include"]
                if isinstance(include, str):
                    include = [include, ]
                elif not isinstance(include, list):
                    elog.error("Item '{0}', Attribute 'se_manual_include': Value must be a string or a list!", item_id)
                    return retval_no_trigger
                elog.info("checking include values: {0}", include)
                elog.increase_indent()

                # If current value is in list -> Return "Trigger"
                for entry in include:
                    entry = re.compile(entry, re.IGNORECASE)
                    result = entry.match(original)
                    elog.info("Checking regex result {}", result)
                    if result is not None:
                        elog.info("{0}: matching. Writing value {1}", entry, retval_trigger)
                        return retval_trigger
                    elog.info("{0}: not matching", entry)
                elog.decrease_indent()

                # Current value not in list -> Return "No Trigger
                elog.info("No include values matching. Writing value {0}", retval_no_trigger)
                return retval_no_trigger
            else:
                # No include-entries -> return "Trigger"
                elog.info("No include limitation. Writing value {0}", retval_trigger)
                return retval_trigger
        finally:
            lock.release()
