apiurl|/api/behaviors/preview
description|play doorbell routine
json|{"behaviorId": "PREVIEW", "status": "ENABLED", "sequenceJson": {"@type": "com.amazon.alexa.behaviors.model.Sequence", "sequenceId": "amzn1.alexa.sequence.8d9b40ab-91a7-46c1-8d42-1cd53408874f", "startNode": {"@type": "com.amazon.alexa.behaviors.model.SerialNode", "name": null, "nodesToExecute": [{"@type": "com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode", "nodeState": null, "name": null, "type": "Alexa.DeviceControls.Volume", "skillId": "amzn1.ask.1p.alexadevicecontrols", "operationPayload": {"customerId": "<deviceOwnerCustomerId>", "deviceType": "<deviceType>", "deviceSerialNumber": "<serialNumber>", "value": 80, "locale": "de-DE"}, "presentationDataList": null, "clientData": null, "context": null, "tag": null}, {"@type": "com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode", "nodeState": null, "name": null, "type": "Alexa.Sound", "skillId": "amzn1.ask.1p.sound", "operationPayload": {"customerId": "<deviceOwnerCustomerId>", "deviceType": "<deviceType>", "deviceSerialNumber": "<serialNumber>", "soundStringId": "amzn_sfx_doorbell_chime_02", "locale": "de-DE"}, "presentationDataList": null, "clientData": null, "context": null, "tag": null}, {"@type": "com.amazon.alexa.behaviors.model.OpaquePayloadOperationNode", "nodeState": null, "name": null, "type": "Alexa.DeviceControls.Volume", "skillId": "amzn1.ask.1p.alexadevicecontrols", "operationPayload": {"customerId": "<deviceOwnerCustomerId>", "deviceType": "<deviceType>", "deviceSerialNumber": "<serialNumber>", "value": 20, "locale": "de-DE"}, "presentationDataList": null, "clientData": null, "context": null, "tag": null}]}}}
