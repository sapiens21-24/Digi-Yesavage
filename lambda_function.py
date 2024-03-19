# -*- coding: utf-8 -*-
"""Simple fact sample app."""

import random
import logging
import json
import prompts
import os
import boto3
import time

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import (
    AbstractRequestHandler, AbstractExceptionHandler,
    AbstractRequestInterceptor, AbstractResponseInterceptor)
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

from ask_sdk_model.ui import SimpleCard
from ask_sdk_model import Response
# --------------------------------------------------------------------- # 
# Clase Status donde guardaremos el progreso globals
# Clase Result donde guardaremos el progreso de cada pregunta
from status import *
from result import *

# Configuración de la persistencia
from ask_sdk_dynamodb.adapter import DynamoDbAdapter
from ask_sdk_core.skill_builder import CustomSkillBuilder
ddb_region          = os.environ.get('DYNAMODB_PERSISTENCE_REGION')
ddb_table_name      = os.environ.get('DYNAMODB_PERSISTENCE_TABLE_NAME')

ddb_resource        = boto3.resource('dynamodb', region_name=ddb_region)
dynamodb_adapter    = DynamoDbAdapter(table_name=ddb_table_name, create_table=False, dynamodb_resource=ddb_resource)

# sb = SkillBuilder() // En nuestro caso debe ser CustomSkillBuilder
sb = CustomSkillBuilder(persistence_adapter = dynamodb_adapter)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


DELAY   = {
    'low'    :[4.130, 4.560, 3.000, 2.370, 3.090, 4.060, 2.550, 4.160, 6.010, 3.570, 3.490, 3.110, 1.570, 3.490, 5.100],
    'normal' :[3.480, 3.530, 2.090, 1.580, 2.510, 3.060, 2.040, 3.110, 4.520, 3.010, 2.530, 2.150, 1.520, 2.570, 4.030],   # Tiempos (x1) Normal
    'fast'   :[]
}

SCORE_Yes_15   = [NO, YES, YES, YES, NO, YES,  NO, YES, YES, YES, NO, YES, NO, YES, YES]

class YesIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.YesIntent")(handler_input)

    def handle(self, handler_input):
        session_attr    = handler_input.attributes_manager.session_attributes
        status_obj      =  Status(status = session_attr['objeto'])
        
        tiempo_actual = time.time()
        delay = DELAY['normal'][status_obj.current_item-1] # -1 Pues la lista empieza en 0

        result        = status_obj.results[status_obj.current_item]
        result.answer = YES
        result.time   = tiempo_actual - (status_obj.t_ini_q + delay)
        
        session_attr['objeto'] = status_obj.to_dict() 
        return NextIntentHandler().handle(handler_input)

class NoIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.NoIntent")(handler_input)

    def handle(self, handler_input):
        session_attr = handler_input.attributes_manager.session_attributes
        status_obj      =  Status(status = session_attr['objeto'])
        
        tiempo_actual = time.time()
        delay = DELAY['normal'][status_obj.current_item-1]

        result        = status_obj.results[status_obj.current_item]
        result.answer = NO
        result.time   = tiempo_actual - (status_obj.t_ini_q + delay)

        status_obj.t_ini_q      = tiempo_actual
        
        if status_obj.current_item < Q1:
            session_attr['objeto'] = status_obj.to_dict()
            return RepeatIntentHandler().handle(handler_input)
        else:
            session_attr['objeto'] = status_obj.to_dict() 
            return NextIntentHandler().handle(handler_input)

class StartTestHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        data                = handler_input.attributes_manager.request_attributes["_"]
        persistence_attr    = handler_input.attributes_manager.persistent_attributes
        handler_input.attributes_manager.session_attributes = persistence_attr
        session_attr         = handler_input.attributes_manager.session_attributes
        
        if 'objeto' in persistence_attr:
            return RepeatIntentHandler().handle(handler_input)
        else:
            session_attr['objeto']       = Status(t_ini = time.time()).to_dict()
            status_obj      =  Status(status = session_attr['objeto'])
            return handler_input.response_builder.speak(data[prompts.KEYS[WELLCOME]]).ask(data[prompts.KEYS[WELLCOME]]).response

class NextIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.NextIntent")(handler_input)

    def handle(self, handler_input):
        data            = handler_input.attributes_manager.request_attributes["_"]
        session_attr    = handler_input.attributes_manager.session_attributes
        status_obj      = Status(status = session_attr['objeto'])
        
        if (status_obj.current_item < Q15):
            status_obj.current_item += 1
            status_obj.t_ini_q      = time.time()
            
            session_attr['objeto'] = status_obj.to_dict()
            handler_input.attributes_manager.persistent_attributes = session_attr
            handler_input.attributes_manager.save_persistent_attributes()
            
            return (
                handler_input.response_builder
                    .speak(data[prompts.KEYS[status_obj.current_item]])
                    .ask(data[prompts.KEYS[status_obj.current_item]])
                    .response
            )
        else:
            Current_ITEM    = str(status_obj.current_item)
            lista_ans = results_to_list_answers(status_obj)

            final_score  = set_final_score( lista_ans, SCORE_Yes_15)
            status_obj = update_results_score(lista_ans, SCORE_Yes_15, status_obj)
            status_obj.final_score      = final_score
            status_obj.t_end            = time.time()
            
            skill_total_time            = status_obj.t_end  - status_obj.t_ini

            session_attr['objeto']          = status_obj.to_dict() # actualizar la sesion con el objeto
            session_attr['objeto_t_ini']    = format_time(status_obj.t_ini)
            session_attr['objeto_t_end']    = format_time(status_obj.t_end)
            session_attr['objeto_t_total']  = format_time(skill_total_time)
                        
            handler_input.attributes_manager.persistent_attributes = session_attr
            handler_input.attributes_manager.save_persistent_attributes()
            
            return handler_input.response_builder.speak(data[prompts.GET_Bye]).response

class RepeatIntentHandler(AbstractRequestHandler):
    """Handler for Repeat Intent."""
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.RepeatIntent")(handler_input)

    def handle(self, handler_input):
    
        data = handler_input.attributes_manager.request_attributes["_"]
        session_attr = handler_input.attributes_manager.session_attributes
        status_obj      =  Status(status = session_attr['objeto'])

        if status_obj.current_item >= Q1:
            status_obj.results[status_obj.current_item].repe += 1
            session_attr['objeto'] = status_obj.to_dict() # actualizar la sesion con el objeto
        return handler_input.response_builder.speak(data[prompts.KEYS[status_obj.current_item]]).ask(data[prompts.KEYS[status_obj.current_item]]).response

class HelpIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In HelpIntentHandler")

        # get localization data
        data = handler_input.attributes_manager.request_attributes["_"]

        speech = data[prompts.HELP_MESSAGE]
        reprompt = data[prompts.HELP_REPROMPT]
        handler_input.response_builder.speak(speech).ask(
            reprompt).set_card(SimpleCard(
                data[prompts.SKILL_NAME], speech))
        
        return handler_input.response_builder.response

class CancelOrStopIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CancelOrStopIntentHandler")

        # get localization data
        data = handler_input.attributes_manager.request_attributes["_"]

        speech = data[prompts.STOP_MESSAGE]
        handler_input.response_builder.speak(speech)

        return handler_input.response_builder.response

class FallbackIntentHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        #return is_intent_name("AMAZON.FallbackIntent")(handler_input)
        return True

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In FallbackIntentHandler")

        return RepeatIntentHandler().handle(handler_input)

class LocalizationInterceptor(AbstractRequestInterceptor):

    def process(self, handler_input):
        locale = handler_input.request_envelope.request.locale
        logger.info("Locale is {}".format(locale))

        # localized strings stored in language_strings.json
        with open("language_strings.json") as language_prompts:
            language_data = json.load(language_prompts)
        # set default translation data to broader translation
        if locale[:2] in language_data:
            data = language_data[locale[:2]]
            # if a more specialized translation exists, then select it instead
            # example: "fr-CA" will pick "fr" translations first, but if "fr-CA" translation exists,
            # then pick that instead
            if locale in language_data:
                data.update(language_data[locale])
        else:
            data = language_data[locale]
        handler_input.attributes_manager.request_attributes["_"] = data

class SessionEndedRequestHandler(AbstractRequestHandler):

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In SessionEndedRequestHandler")

        logger.info("Session ended reason: {}".format(
            handler_input.request_envelope.request.reason))
        return handler_input.response_builder.response

# Exception Handler
class CatchAllExceptionHandler(AbstractExceptionHandler):

    def can_handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> bool
        return True

    def handle(self, handler_input, exception):
        # type: (HandlerInput, Exception) -> Response
        logger.info("In CatchAllExceptionHandler")
        logger.error(exception, exc_info=True)
        
        data = handler_input.attributes_manager.request_attributes["_"]

        # handler_input.response_builder.speak(EXCEPTION_MESSAGE).ask(
        handler_input.response_builder.speak(data[prompts.GET_EXCEPTION_TEST]).ask(
            data[prompts.GET_EXCEPTION_TEST])

        return handler_input.response_builder.response

# Request and Response loggers
class RequestLogger(AbstractRequestInterceptor):
    """Log the alexa requests."""

    def process(self, handler_input):
        # type: (HandlerInput) -> None
        logger.info("Alexa Request: {}".format(
            handler_input.request_envelope.request))

class ResponseLogger(AbstractResponseInterceptor):
    """Log the alexa responses."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.debug("Alexa Response: {}".format(response))

# Register intent handlers
sb.add_request_handler(YesIntentHandler())
sb.add_request_handler(NoIntentHandler())
sb.add_request_handler(StartTestHandler())
sb.add_request_handler(NextIntentHandler())
sb.add_request_handler(RepeatIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

# Register exception handlers
sb.add_exception_handler(CatchAllExceptionHandler())

# Register request and response interceptors
sb.add_global_request_interceptor(LocalizationInterceptor())
sb.add_global_request_interceptor(RequestLogger())
sb.add_global_response_interceptor(ResponseLogger())

# Handler name that is used on AWS lambda
lambda_handler = sb.lambda_handler()
