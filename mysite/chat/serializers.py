import injections
from rest_framework import serializers
from django.core.urlresolvers import reverse

from .models import Message, Chat
from .services import ProgressHandler
from ct.models import UnitLesson, Response


class InternalMessageSerializer(serializers.ModelSerializer):
    """
    Serializer for addMessage list representation.
    """
    html = serializers.CharField(source='get_html', read_only=True)
    name = serializers.CharField(source='get_name', read_only=True)
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id',
            'type',
            'name',
            'userMessage',
            'avatar',
            'html'
        )

    def get_avatar(self, obj):
        return '/static/img/avatar-teacher.jpg'


class InputSerializer(serializers.Serializer):
    """
    Serializer for input description for next message.
    """
    type = serializers.CharField(max_length=16, read_only=True)
    url = serializers.CharField(max_length=64, read_only=True)
    options = serializers.ListField()
    includeSelectedValuesFromMessages = serializers.ListField(
        child=serializers.IntegerField(min_value=0)
    )


@injections.has
class MessageSerializer(serializers.ModelSerializer):
    """
    Message serializer.
    """
    next_handler = injections.depends(ProgressHandler)

    input = serializers.SerializerMethodField()
    # errors = serializers.CharField(source='get_errors', read_only=True)
    addMessages = serializers.SerializerMethodField()
    nextMessagesUrl = serializers.CharField(source='get_next_url', read_only=True)

    class Meta:
        model = Message
        fields = (
            'id',
            'input',
            'addMessages',
            'nextMessagesUrl',
            # 'errors',
        )

    def set_group(self, obj):
        try:
            getattr(self, 'qs')
        except AttributeError:
            print('Inside')
            self.qs = [obj]
            if obj.timestamp:
                current = obj
                for message in obj.chat.message_set.filter(timestamp__gt=obj.timestamp):
                    if self.next_handler.group_filter(current, message):
                        current = message
                        self.qs.append(message)

    def get_input(self, obj):
        """
        Getting description for next message.
        """
        self.set_group(obj)
        input_data = {
            'type': obj.get_next_input_type(),
            'url': obj.get_next_url(),
            'options': obj.get_options(),
            'includeSelectedValuesFromMessages': [i.id for i in self.qs if i.contenttype == 'uniterror']
        }
        return InputSerializer().to_representation(input_data)

    def get_addMessages(self, obj):
        print('get_messages')
        self.set_group(obj)
        return InternalMessageSerializer(many=True).to_representation(self.qs)


class ChatHistorySerializer(serializers.ModelSerializer):
    """
    Serializer to implement /history API.
    """
    input = serializers.SerializerMethodField()
    addMessages = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = (
            'input',
            'addMessages',
        )

    def get_input(self, obj):
        """
        Getting description for next message.
        """
        input_data = {
            'type': obj.next_point.input_type,
            'url': reverse('chat:messages-detail', args=(obj.next_point.id,)),
            'options': obj.get_options(),
            # for test purpose only
            'includeSelectedValuesFromMessages': []
        }
        return InputSerializer().to_representation(input_data)

    def get_addMessages(self, obj):
        return InternalMessageSerializer(many=True).to_representation(
            obj.message_set.all().exclude(timestamp__isnull=True).order_by('timestamp')
        )


class LessonSerializer(serializers.ModelSerializer):
    """
    Serializer for Lesson.
    """
    html = serializers.CharField(source='lesson.title', read_only=True)
    isDone = serializers.SerializerMethodField()
    isUnlocked = serializers.SerializerMethodField()

    class Meta:
        model = UnitLesson
        fields = (
            'id',
            'html',
            'isUnlocked',
            'isDone'
        )

    def get_isUnlocked(self, obj):
        if hasattr(obj, 'message'):
            message = Message.objects.get(id=obj.message)
            return message.timestamp is not None
        else:
            return False

    def get_isDone(self, obj):
        if hasattr(obj, 'message'):
            message = Message.objects.get(id=obj.message)
            last_message = Message.objects.filter(chat=message.chat,
                                                  timestamp__isnull=False)\
                                          .order_by('timestamp').last()
            return message.timestamp is not None and not message.timestamp == last_message.timestamp
        else:
            return False


class ChatProgressSerializer(serializers.ModelSerializer):
    """
    Serializer to implement /progress API.
    """
    breakpoints = serializers.SerializerMethodField()
    progress = serializers.SerializerMethodField()

    lessons_dict = None

    class Meta:
        model = Chat
        fields = (
            'progress',
            'breakpoints',
        )

    def get_breakpoints(self, obj):
        if not self.lessons_dict:
            messages = obj.message_set.filter(contenttype='unitlesson')
            lessons = list(obj.enroll_code.courseUnit.unit.unitlesson_set.filter(order__isnull=False))
            for each in messages:
                if each.content in lessons:
                    lessons[lessons.index(each.content)].message = each.id
                else:
                    if each.content.kind != 'answers':
                        lesson = each.content
                        lesson.message = each.id
                        lessons.append(lesson)
            self.lessons_dict = LessonSerializer(many=True).to_representation(lessons)
        return self.lessons_dict

    def get_progress(self, obj):
        if not self.lessons_dict:
            self.get_breakpoints(obj)
        done = reduce(lambda x, y: x+y, map(lambda x: x['isDone'], self.lessons_dict))
        return round(float(done)/len(self.lessons_dict), 2)
