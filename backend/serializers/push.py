from collections import OrderedDict

from rest_framework import serializers
from django.utils.translation import activate, ugettext as _

from sportloto.settings import LANGUAGES


class PushAction():
    GAME_UPDATED = 'game_updated'


class PushMessage(serializers.Serializer):
    __is_localized__ = False

    def __init__(self, *args, **kwargs):
        self.__is_localized__ = kwargs.pop('is_localized', False)

        super(PushMessage, self).__init__(*args, **kwargs)

    #Fields
    action = serializers.SerializerMethodField(read_only=True)
    message = serializers.SerializerMethodField(method_name='build_message', read_only=True)
    data = serializers.DictField(required=True)

    def build_message(self, *args, **kwarg):
        if self.__is_localized__:
            result = {}

            for language in LANGUAGES:
                lang_code, lang_name = language

                activate(lang_code)
                result[lang_code] = _(self.message_text())
        else:
            result = self.message_text()

        return result

    @staticmethod
    def message_text():
        raise NotImplementedError()

    def get_action(self, *args, **kwargs):
        raise NotImplementedError()


class GameUpdatedPushMessage(PushMessage):

    def __init__(self, *args, **kwargs):
        from backend.models import Game
        from backend.serializers.game import PublicGameSerializer

        payload = kwargs.pop('payload', None)

        if not isinstance(payload, Game):
            raise AttributeError('payload should be instance of Game model')

        serializer = PublicGameSerializer(payload)

        data = kwargs.get('data', {})

        #Data field in payload
        data['data'] = OrderedDict(serializer.data)

        kwargs['data'] = data

        super(GameUpdatedPushMessage, self).__init__(*args, **kwargs)

    @staticmethod
    def message_text():
        return 'Game updated!'

    def get_action(self, *args, **kwargs):
        return PushAction.GAME_UPDATED