from rest_framework import serializers
from web3.main import Web3

from backend.models import Game, ExchangeRate
from backend.serializers import push
from backend.serializers.device import DeviceOS
from backend.serializers.push import PushAction


class FiatExchangeCalculatorMixin():
    def convert_amount_to_fiat(self, obj, attribute_name='prize_amount'):
        """
        :param obj:
        :type obj: Game|dict
        :return: float
        """

        if type(obj) is dict:
            amount = float(obj[attribute_name])
        else:
            amount = float(getattr(obj, attribute_name, 0))

        if amount <= 0:
            return 0

        return self.calculate_fiat_amount(amount)

    def calculate_fiat_amount(self, amount):
        latest_exchange_rate = ExchangeRate.objects.order_by('-created_at').first()
        """
        :var latest_exchange_rate:
        :type latest_exchange_rate: ExchangeRate
        """

        return (amount * float(latest_exchange_rate.rate))


class PublicGameSerializer(serializers.ModelSerializer, FiatExchangeCalculatorMixin):
    __stat__ = None
    """
    :var __stats__:
    :type dict:
    """

    def get_gas_price(self, obj):
        return 0 if obj.type in (Game.TYPE_30_DAYS, Game.TOKEN_GAME) else 2

    def get_gas_limit(self, obj):
        return 0 if obj.type in (Game.TYPE_30_DAYS, Game.TOKEN_GAME) else 90000

    prize_amount_fiat = serializers.SerializerMethodField(read_only=True)
    bet_amount = serializers.SerializerMethodField(read_only=True)
    bet_amount_fiat = serializers.SerializerMethodField(read_only=True)
    num_players = serializers.SerializerMethodField(read_only=True)
    prize_amount = serializers.SerializerMethodField(read_only=True)
    gas_price = serializers.SerializerMethodField(read_only=True)
    gas_limit = serializers.SerializerMethodField(read_only=True)

    def __get_stat__(self, game):
        key = 'g%d' % (game.id)

        if self.__stat__ is None:
            self.__stat__ = {}

        if self.__stat__.get(key, None) is None:
            self.__stat__[key] = game.get_stat()

        return self.__stat__.get(key)

    def get_num_players(self, obj):
        try:
            stat = self.__get_stat__(obj)
        except:
            stat = {}

        return int(stat.get('numPlayers', getattr(obj, 'num_players')))

    def get_prize_amount(self, obj):
        result = 0

        try:
            stat = self.__get_stat__(obj)
            result = Web3.fromWei(stat.get('prizeAmount'), 'ether')
        except:
            result = float(getattr(obj, 'prize_amount'))

        return {
            'amount': float(result),
            'currency': 'UNIT' if obj.type == Game.TOKEN_GAME else 'ETH'
        }

    def get_prize_amount_fiat(self, obj):
        amount = self.get_prize_amount(obj).get('amount', 0)

        if obj.type == Game.TOKEN_GAME:
            amount *= 0.000079

        return self.calculate_fiat_amount(amount)

    def get_bet_amount_fiat(self, obj):
        return self.convert_amount_to_fiat(obj, attribute_name='bet_amount')

    def get_bet_amount(self, obj):
        return {
            'amount': 0 if obj.type in (Game.TOKEN_GAME, Game.TYPE_30_DAYS) else obj.bet_amount,
            'currency': 'ETH'
        }

    class Meta:
        model = Game
        fields = ('id', 'status', 'type', 'smart_contract_id', 'prize_amount', 'prize_amount_fiat', 'num_players',
                  'bet_amount', 'bet_amount_fiat', 'gas_price', 'gas_limit', 'started_at', 'ending_at',)


class GameWinner(serializers.Serializer, FiatExchangeCalculatorMixin):
    address = serializers.CharField()
    position = serializers.IntegerField()
    prize_amount = serializers.DictField()
    prize_amount_fiat = serializers.SerializerMethodField()

    def get_prize_amount_fiat(self, obj):
        amount = obj.get('prize_amount', {'amount':0, 'currency': 'ETH'})

        if amount.get('currency') == 'UNIT':
            amount['amount'] = float(amount.get('amount')) * 0.000079

        return self.convert_amount_to_fiat(amount, 'amount')


class GameDebugPush(serializers.Serializer):
    os = serializers.ChoiceField(choices=DeviceOS.CHOICES, required=False)
    token = serializers.CharField(required=False)
    action = serializers.ChoiceField(choices=PushAction.CHOICES, required=True)

    def get_push_message(self, type, game):
        """
        :param type:
        :type str:
        :param game:
        :type Game:
        :rtype push.PushMessage:
        """
        cls_map = {
            PushAction.GAME_STARTED: push.GameStartedPushMessage,
            PushAction.GAME_UPDATED: push.GameUpdatedPushMessage,
            PushAction.GAME_UNPUBLISHED: push.GameUnpublishedPushMessage,
            PushAction.GAME_FINISHED: push.GameFinishedPushMessage
        }

        cls = cls_map.get(type, None)

        if cls is None:
            raise AttributeError('Type "%s" is invalid' % (type))

        return cls(payload=game)
