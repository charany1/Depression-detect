import os
import logging
from ask_sdk.standard import StandardSkillBuilder
from ask_sdk_core.utils import is_intent_name, is_request_type
import ask_sdk_dynamodb
from ask_sdk_core.dispatch_components import AbstractRequestHandler, AbstractExceptionHandler, \
    AbstractRequestInterceptor, AbstractResponseInterceptor
from ask_sdk_model.ui import SimpleCard

# ==========Data================================
STOP_MESSAGE = "Take Care,Bye"

questions_list = ["Little interest or pleasure in doing things",
                  " down, depressed, or hopeless",
                  "Trouble falling or staying asleep, or sleeping too much",
                  "Tired or having little energy",
                  "Poor appetite or overeating",
                  "Bad about yourself - or that you are a failure or have let yourself or your family down",
                  "Trouble concentrating on things, such as reading the newspaper or watching television",
                  "Like moving or speaking so slowly that other people could have noticed",
                  "Thoughts that you would be better off dead, or of hurting yourself",
                  ]
first_question_starter = " Think over last two weeks "
question_beginner = " For how many days have you been feeling , "

# todo below questions can be asked conditionally i.e. if user replied a non-None response to any of the questions
# that would make it conversational
# how_much_difficulty_question="How difficult have these problems made it for you at work, home, school, " \
# "or with other people"
# difficulty_question_beginner= "Okay , final question ,"
# how_much_difficulty_question_responses=["No difficulty","Somewhat difficult","Very difficult","Extremely difficult"]

help_message = "Try to reply to the questions I ask by considering time span of last two weeks,Your responses " \
               "could be one of None , Several , More than half , Almost everyday ."

help_message_example = "For example , for the question: " + question_beginner + questions_list[
    0] + " you can respond by " \
         "saying None , Several ,More than half,Almost everyday "

# ================================================

# todo Figure out how to import questions module had it been in a different package question
skill_persistence_table = os.environ["skill_persistence_table"]

SKILL_NAME = 'Depression Detect'
launch_message = f"Welcome to {SKILL_NAME} , I can help you detect depression "
prompt = "can we proceed ?"
skill_builder = StandardSkillBuilder(table_name=skill_persistence_table, auto_create_table=False,
                                     partition_keygen=ask_sdk_dynamodb.partition_keygen.user_id_partition_keygen)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


# Built-in Intent Handlers
class LaunchSkillHandler(AbstractRequestHandler):
    """Handler for Skill Launch and OpenDepressionDetect Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_request_type("LaunchRequest")(handler_input) or
                is_intent_name("OpenDepressionDetectIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In LaunchSkillHandler#handle")
        attr = handler_input.attributes_manager.persistent_attributes
        if not attr:
            logger.debug("Persistent attributes not found,initializing session attributes with default starting values")
            attr['question_to_ask_next'] = 0
            attr['all_question_answered'] = False
            attr['score_so_far'] = 0
            print("session attr : ", attr)
            handler_input.attributes_manager.session_attributes = attr
        else:
            logger.debug("Persistent attributes found,setting session attributes to persistent attributes")
            handler_input.attributes_manager.session_attributes = handler_input.attributes_manager.persistent_attributes
            print(handler_input.attributes_manager.session_attributes)

        speech = launch_message + ',' + prompt
        handler_input.response_builder.speak(speech).set_card(
            SimpleCard(SKILL_NAME, speech))
        handler_input.response_builder.set_should_end_session(False)
        return handler_input.response_builder.response


class StartOrContinueQuestionsHandler(AbstractRequestHandler):
    """Handler for asking first question after user has said Yes to our prompt for proceeding"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.YesIntent")(handler_input) or
                is_intent_name("ContinueIntent")(handler_input))
    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In StartOrContinueQuestionsHandler#handle")
        session_attr = handler_input.attributes_manager.session_attributes
        if session_attr['all_question_answered']:
            speech = "You have already answered all questions ,"+get_depression_category_from_score(session_attr['score_so_far'])
        elif session_attr['question_to_ask_next'] == 0:
            speech = first_question_starter + ',' + question_beginner + questions_list[session_attr['question_to_ask_next']]
        else:
            speech = question_beginner + questions_list[session_attr['question_to_ask_next']]
        handler_input.response_builder.speak(speech).set_card(
            SimpleCard(SKILL_NAME, speech))
        handler_input.response_builder.set_should_end_session(False)
        return handler_input.response_builder.response


class QuestionResponseIntentHandler(AbstractRequestHandler):
    """Handler for getting user responses for the questions asked , update score and finally tell the result to user"""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return is_intent_name("QuestionResponseIntent")(handler_input)

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In QuestionResponseIntentHandler#handle")
        resolved_value = get_resolved_value(handler_input.request_envelope.request, "response")
        print("Res-val : " + resolved_value)
        session_attr = handler_input.attributes_manager.session_attributes
        score = score_for_this_question(resolved_value)
        print("Score for previous question : ",score)
        print("Session attr : ",session_attr)
        if score != -1:
            session_attr['question_to_ask_next'] += 1
            session_attr['score_so_far'] += score
            if session_attr['question_to_ask_next'] < 9:
                speech = question_beginner + questions_list[session_attr['question_to_ask_next']]
            elif session_attr['question_to_ask_next'] == 9:
                speech = "Thank you for completing the test," + get_depression_category_from_score(session_attr
                                                                                     ['score_so_far'])+','+STOP_MESSAGE
                session_attr['all_question_answered'] = True
                persist_user_attributes(handler_input)

        else:
            speech = "Sorry , didn't got you , please speak again"
        print("speech from QuestionResponseIntentHandler#handle",speech)
        handler_input.response_builder.speak(speech).set_card(SimpleCard(SKILL_NAME, speech))
        if session_attr['all_question_answered']:
            handler_input.response_builder.set_should_end_session(True)
        else:
            handler_input.response_builder.set_should_end_session(False)
        return handler_input.response_builder.response


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""

    def can_handle(self, handler_input):
        # type: (HandlerInput) -> bool
        return (is_intent_name("AMAZON.CancelIntent")(handler_input) or
                is_intent_name("AMAZON.StopIntent")(handler_input) or
                is_intent_name("AMAZON.NoIntent")(handler_input))

    def handle(self, handler_input):
        # type: (HandlerInput) -> Response
        logger.info("In CancelOrStopOrNoIntentHandler")
        persist_user_attributes(handler_input)
        handler_input.response_builder.speak(STOP_MESSAGE)
        return handler_input.response_builder.response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        logger.info(f"Reason for ending session : {handler_input.request_envelope.request.reason}")
        persist_user_attributes(handler_input)
        return handler_input.response_builder.response


class StartOverIntentHandler(AbstractRequestHandler):
    def can_handle(self,handler_input):
        return is_intent_name("AMAZON.StartOverIntent")(handler_input)
    
    def handle(self,handler_input):
        """restarts asking questions from the beginning"""
        session_attr = handler_input.attributes_manager.session_attributes
        session_attr['question_to_ask_next'] = 0
        session_attr['all_question_answered'] = False
        session_attr['score_so_far'] = 0
        handler_input.attributes_manager.persistent_attributes = session_attr
        persist_user_attributes(handler_input)
        logger.info("In StartOverIntentHandler#handle")
        question_one = first_question_starter + ',' + question_beginner + questions_list[0]
        speech = question_one
        handler_input.response_builder.speak(speech).set_card(
            SimpleCard(SKILL_NAME, speech))
        handler_input.response_builder.set_should_end_session(False)
        return handler_input.response_builder.response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self,handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self,handler_input):
        logger.info("In HelpIntentHandler#handle")
        speech = help_message + help_message_example
        reprompt = "Can we start ?"
        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response

class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self,handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self,handler_input):
        speech = "Sorry , I didn't got you , I can help you detect depression ."
        reprompt = "You can say continue or start over"

        handler_input.response_builder.speak(speech).ask(reprompt)
        return handler_input.response_builder.response




class ResponseLogger(AbstractResponseInterceptor):
    """Log the alexa responses."""

    def process(self, handler_input, response):
        # type: (HandlerInput, Response) -> None
        logger.debug("Alexa Response: {}".format(response))


skill_builder.add_request_handler(LaunchSkillHandler())
skill_builder.add_request_handler(CancelOrStopIntentHandler())
skill_builder.add_request_handler(StartOrContinueQuestionsHandler())
skill_builder.add_request_handler(QuestionResponseIntentHandler())
skill_builder.add_request_handler(SessionEndedRequestHandler())
skill_builder.add_request_handler(StartOverIntentHandler())
skill_builder.add_request_handler(HelpIntentHandler())
skill_builder.add_request_handler(FallbackIntentHandler())


# Utility functions

def get_depression_category_from_score(score):
    """

    :rtype: str
    """
    if 0 <= score <= 4:
        return "You don't have depression!"
    elif 5 <= score <= 9:
        return "You might have mild depression"
    elif 10 <= score <= 14:
        return "You might have moderate depression"
    elif 15 <= score <= 19:
        return "You have chances of having moderately severe depression"
    elif 20 <= score <= 27:
        return "Sorry to say, you might be having severe depression , please consult a psychiatrist at the earliest"
    else:
        logger.info("Couldn't calculate score for user")
        return "Sorry,I couldn't calculate your depression level,please try retaking the test"


def score_for_this_question(response):
    """Returns PHQ-9 score for the response given by the user to the question asked"""
    if (response == "None"):
        return 0
    elif (response == "Several"):
        return 1
    elif (response == "More than half"):
        return 2
    elif (response == "Everyday"):
        return 3
    else:
        logger.debug("Invalid response , returning -1")
        return -1


def get_resolved_value(request, slot_name):
    """Resolve the slot name from the request using resolutions."""
    # type: (IntentRequest, str) -> Union[str, None]
    try:
        return (request.intent.slots[slot_name].resolutions.
                resolutions_per_authority[0].values[0].value.name)
    except (AttributeError, ValueError, KeyError, IndexError, TypeError) as e:
        logger.info("Couldn't resolve {} for request: {}".format(slot_name, request))
        logger.info(str(e))
        return None


def persist_user_attributes(handler_input):
    session_attr = handler_input.attributes_manager.session_attributes
    handler_input.attributes_manager.persistent_attributes = session_attr
    handler_input.attributes_manager.save_persistent_attributes()


# skill_builder.add_global_request_interceptor(RequestLogger())
# skill_builder.add_global_response_interceptor(ResponseLogger())

lambda_handler = skill_builder.lambda_handler()




