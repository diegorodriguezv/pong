#!/bin/env/python
"""Pong game: """
import ctypes
import math
import os
import random
import time
from array import array
from collections import namedtuple
from functools import partialmethod

import pygame
from pygame.locals import *
from pygame.mixer import Sound, get_init, pre_init


def one_period_square_wave_samples(frequency):
    sample_rate = get_init()[0]
    period = int(round(sample_rate / frequency))
    samples = array("h", [0] * period)
    amplitude = 2 ** (abs(get_init()[1]) - 1) - 1
    for time in range(period):
        if time < period / 2:
            samples[time] = amplitude
        else:
            samples[time] = -amplitude
    return samples


def precompute(build_samples_func, frequency, milliseconds):
    sample_rate = get_init()[0]
    samples = build_samples_func(frequency)
    samples_milliseconds = len(samples) / sample_rate * 1000
    copies = math.ceil(milliseconds / samples_milliseconds)
    result = samples * copies
    return result


Position = namedtuple('Position', 'x y')
Vector = namedtuple('Vector', 'x y')
Size = namedtuple('Size', 'width height')
Area = namedtuple('Area', 'position size')


def pretty_float_pair(self, name, labels):
    """If labels = ('a', 'b') and object = (1.2345, 1.2345) returns:
        'name(a=1.23, b=1.23)'"""
    return '{}({}={:.2f}, {}={:.2f})'.format(name, labels[0], self[0], labels[1], self[1])


Position.__str__ = partialmethod(pretty_float_pair, 'Position', ('x', 'y'))
Vector.__str__ = partialmethod(pretty_float_pair, 'Vector', ('x', 'y'))
Size.__str__ = partialmethod(pretty_float_pair, 'Size', ('width', 'height'))


class Direction:
    Up = 0
    Down = 1
    Left = 2
    Right = 3


class Color:
    Transparent = (0, 0, 0, 0)
    Black = (0, 0, 0)
    LightGray = (192, 192, 192)
    HalfGray = (128, 128, 128)
    DarkGray = (192, 192, 192)
    White = (255, 255, 255)
    Red = (255, 0, 0)
    Green = (0, 255, 0)
    Blue = (0, 0, 255)


class ColorPalette(Color):
    Paddle = Color.DarkGray
    Score = Color.LightGray
    Ball = Color.White
    HalfLine = Color.White
    Background = Color.Black


def pixel_scale(pos):
    x, y = pos
    return Position(int(x / field_size.width * win_w), int(y / field_size.height * win_h))


class Sprite:
    def __init__(self):
        self.position = Position(0, 0)
        self.last_draw_position = self.position
        self.prev_position = self.position
        self.size = Size(1, 1)
        self.speed = Vector(0, 0)
        self.min_speed = 0
        self.max_speed = 1
        self.color = ColorPalette.Green

    def update(self):
        self.prev_position = self.position
        self.position = self.interpolate_next_position(alpha=1)

    def interpolate_next_position(self, alpha):
        return Position(
            self.position.x + self.speed.x * delta * alpha,
            self.position.y + self.speed.y * delta * alpha)

    def interpolate_prev_position(self, alpha):
        return Position(
            self.position.x * alpha + self.prev_position.x * (1 - alpha),
            self.position.y * alpha + self.prev_position.y * (1 - alpha))

    def draw(self, alpha):
        self.last_draw_position = self.interpolate_prev_position(alpha)
        # window.fill() won't work in the edges
        pygame.draw.rect(window, self.color, (pixel_scale(self.last_draw_position), pixel_scale(self.size)))

    def clear(self):
        # window.fill() won't work in the edges
        pygame.draw.rect(window, ColorPalette.Background,
                         (pixel_scale(self.last_draw_position), pixel_scale(self.size)))

    def collides(self, sprite):
        rect1 = Rect(pixel_scale(self.position), pixel_scale(self.size))
        rect2 = Rect(pixel_scale(sprite.position), pixel_scale(sprite.size))
        return rect1.colliderect(rect2)

    def bounce(self, angle):
        # todo: different angle in head and tail
        self.speed = reflect(self.speed, angle)


def magnitude(vector):
    return math.sqrt(vector.x ** 2 + vector.y ** 2)


def slope(vector):
    return math.degrees(math.atan2(vector.y, vector.x))


def reflect(vector, surface_angle):
    # reflected_angle = 2 * surface_angle - incident_angle
    # since a rotation starts at the vector's angle we must subtract it
    # rotation_angle = 2 * surface_angle - incident_angle - incident_angle
    #                = 2 * (surface_angle - incident_angle)
    incident_angle = slope(vector)
    return rotate(vector, 2 * (surface_angle - incident_angle))


def rotate(vector, angle):
    return Vector(
        vector.x * math.cos(math.radians(angle)) - vector.y * math.sin(math.radians(angle)),
        vector.x * math.sin(math.radians(angle)) + vector.y * math.cos(math.radians(angle)))


def center(target, size):
    return target + size / 2


class PaddleParts(object):
    """Represents a bunch of objects with name."""

    def __init__(self, **kw):
        self.__dict__.update(kw)


class Paddle(Sprite):
    def __init__(self, x):
        super().__init__()
        self.size = Size(1, 8)
        self.position = Position(x, center(field_size.height / 2, self.size.height))
        self.min_speed = 6 / 100
        self.color = ColorPalette.Paddle
        self.parts = self.paddle_parts(self.position)

    @staticmethod
    def paddle_parts(position):
        return PaddleParts(
            top=Area(Position(position.x, position.y), Size(1, 1)),
            top_center=Area(Position(position.x, position.y + 1), Size(1, 1)),
            center=Area(Position(position.x, position.y + 2), Size(1, 4)),
            bottom_center=Area(Position(position.x, position.y + 6), Size(1, 1)),
            bottom=Area(Position(position.x, position.y + 7), Size(1, 1)))

    def move(self, input_direction):
        if input_direction == Direction.Up:
            self.speed = Vector(0, -self.min_speed)
        elif input_direction == Direction.Down:
            self.speed = Vector(0, self.min_speed)
        else:
            self.speed = Vector(0, 0)

    def update(self):
        # restrict paddle movement
        last_pos = self.position
        super().update()
        if self.position.y < -self.size.height + 1 or self.position.y > field_size.height - 1:
            self.position = last_pos
        self.parts = self.paddle_parts(self.position)

    def reflection_angle(self, sprite):
        sprite_rect = Rect(pixel_scale(sprite.position), pixel_scale(sprite.size))
        if sprite_rect.colliderect(
                (pixel_scale(self.parts.top.position), pixel_scale(self.parts.top.size))):
            return 90
        elif sprite_rect.colliderect(
                (pixel_scale(self.parts.bottom.position), pixel_scale(self.parts.bottom.size))):
            return 90
        elif sprite_rect.colliderect(
                (pixel_scale(self.parts.top_center.position), pixel_scale(self.parts.top_center.size))):
            return 90
        elif sprite_rect.colliderect(
                (pixel_scale(self.parts.bottom_center.position), pixel_scale(self.parts.bottom_center.size))):
            return 90
        elif sprite_rect.colliderect(
                (pixel_scale(self.parts.center.position), pixel_scale(self.parts.center.size))):
            return 90
        else:
            raise ValueError("The sprite doesn't collide with the paddle")

    def draw(self, alpha):
        self.last_draw_position = self.interpolate_prev_position(alpha)
        # self.update_parts(self.last_draw_position)
        # self.update()
        colors = (Color.HalfGray, Color.LightGray, Color.White, Color.LightGray, Color.HalfGray)
        parts = (self.parts.top, self.parts.top_center, self.parts.center, self.parts.bottom_center, self.parts.bottom)
        for p, c in zip(parts, colors):
            x, y = pixel_scale(p.position)
            w, h = pixel_scale(p.size)
            # window.fill() won't work in the edges
            pygame.draw.rect(window, c, (x, y, w, h))


class Ball(Sprite):
    def __init__(self):
        super().__init__()
        self.size = Size(1, 1)
        self.position = Position(
            center(field_size.width / 2, self.size.width),
            center(field_size.height / 2, self.size.height))
        self.min_speed = 4 / 100
        self.color = ColorPalette.Ball

    def kick_off(self, direction):
        """Kick off from the half line between 5% height from the border. If None direction
        is given, one of the two (Left or Right) will be chosen randomly."""
        self.position = Position(
            center(field_size.width / 2, self.size.width),
            (random.random() * 0.9 + 0.05) * field_size.height)
        if direction is None:
            direction = random.choice([Direction.Left, Direction.Right])
        if direction == Direction.Left:
            self.speed = Vector(
                -self.min_speed,
                (1 - 2 * random.random()) * self.min_speed)
        if direction == Direction.Right:
            self.speed = Vector(
                self.min_speed,
                (1 - 2 * random.random()) * self.min_speed)

    def start_win_screen(self):
        """Kick off from in between 5% from each border."""
        self.position = Position(
            (random.random() * 0.9 + 0.05) * field_size.width,
            (random.random() * 0.9 + 0.05) * field_size.height)
        self.speed = Vector(
            random.choice([1, -1]) * self.min_speed,
            random.choice([1, -1]) * self.min_speed)


def clear_field():
    clear_half_line()
    clear_score()
    clear_fps()
    clear_message()
    clear_limits()


def draw_field():
    draw_half_line()
    draw_score()
    draw_fps()
    draw_message()
    draw_limits()


def draw_limits():
    if show_limits:
        corners = [(1, 1), (field_size.width - 1, 1), (field_size.width - 1, field_size.height - 1),
                   (1, field_size.height - 1)]
        corners.append(corners[0])
        for corner in range(len(corners) - 1):
            start = pixel_scale(corners[corner])
            end = pixel_scale(corners[corner + 1])
            pygame.draw.line(window, ColorPalette.Score, start, end, 1)


def clear_limits():
    corners = [(1, 1), (field_size.width - 1, 1), (field_size.width - 1, field_size.height - 1),
               (1, field_size.height - 1)]
    corners.append(corners[0])
    for corner in range(len(corners) - 1):
        start = pixel_scale(corners[corner])
        end = pixel_scale(corners[corner + 1])
        pygame.draw.line(window, ColorPalette.Background, start, end, 1)


def draw_fps():
    global fps_font
    global text_surface
    if show_fps:
        elapsed = time.clock() - t0
        if elapsed == 0:
            fps = 0.0
        else:
            fps = frame_count / elapsed
        text_surface = fps_font.render('FPS: {:04.2f} - {:04.2f} VT: {:.2f}'.format(
            fps, my_clock.get_fps(), virtual_time), True, Color.Green)
        window.blit(text_surface, (20, 20))


def clear_fps():
    if text_surface is not None:
        x, y, w, h = text_surface.get_rect()
        window.fill(ColorPalette.Background, (20, 20, w, h))


message_surface = None
message = None
message_duration = 3000
ERASEMESSAGE = pygame.USEREVENT + 2


def display_message_duration(new_message):
    global message
    message = new_message
    pygame.time.set_timer(ERASEMESSAGE, message_duration)


def erase_message():
    global message
    if pause:
        message = "PAUSE"
    else:
        message = None
    pygame.time.set_timer(ERASEMESSAGE, 0)


def draw_message():
    global big_font
    global message_surface
    if message is not None:
        message_surface = big_font.render(message, True, Color.Blue)
        box = message_surface.get_rect()
        box.centerx = win_w / 2
        box.centery = win_h / 2
        window.blit(message_surface, box)


def clear_message():
    if message_surface is not None:
        box = message_surface.get_rect()
        box.centerx = win_w / 2
        box.centery = win_h / 2
        window.fill(ColorPalette.Background, box)


def draw_half_line():
    segments = 30
    segment_length = (field_size.height - 1) / segments
    for segment in range(segments):
        start = pixel_scale((field_size.width / 2, segment_length * segment + 1))
        end = pixel_scale((field_size.width / 2, segment_length * segment + (3 / 4 * segment_length)))
        pygame.draw.line(window, ColorPalette.HalfLine, start, end, 2)


def clear_half_line():
    start = pixel_scale((field_size.width / 2, 0))
    end = pixel_scale((field_size.width / 2, field_size.height))
    pygame.draw.line(window, ColorPalette.Background, start, end, 2)


def draw_score():
    left, right = score
    draw_number(left, Position(50, 10), Size(8, 10), ColorPalette.Score)
    draw_number(right, Position(130, 10), Size(8, 10), ColorPalette.Score)


def clear_score():
    left, right = score
    draw_number(left, Position(50, 10), Size(8, 10), ColorPalette.Background)
    draw_number(right, Position(130, 10), Size(8, 10), ColorPalette.Background)


def draw_number(number, pos, size, color):
    digits = str(number)
    x_offset = 10
    next_draw_pos = pos
    for digit in digits:
        draw_digit(int(digit), next_draw_pos, size, color)
        next_draw_pos = Position(next_draw_pos.x + x_offset, next_draw_pos.y)


def draw_digit(digit, pos, size, color):
    # 7 segments:
    #    a
    #    _
    #  f| |b
    #    g
    #    _
    #  e|_|c
    #    d
    if digit == 0:
        segments = 'abcdef'
    elif digit == 1:
        segments = 'bc'
    elif digit == 2:
        segments = 'abdeg'
    elif digit == 3:
        segments = 'abcdg'
    elif digit == 4:
        segments = 'bcfg'
    elif digit == 5:
        segments = 'acdfg'
    elif digit == 6:
        segments = 'acdefg'
    elif digit == 7:
        segments = 'abc'
    elif digit == 8:
        segments = 'abcdefg'
    elif digit == 9:
        segments = 'abcdfg'
    else:
        raise ValueError('Invalid digit: '.format(digit))
    for segment in segments:
        draw_segment(segment, pos, size, color)


def draw_segment(segment, pos, size, color):
    # 7 segments:
    #    a
    #    _
    #  f| |b
    #    g
    #    _
    #  e|_|c
    #    d
    line_width = Position(1, 1)
    left = pos.x
    right = pos.x + size.width
    top = pos.y
    middle = pos.y + size.height * 0.4
    bottom = pos.y + size.height
    if segment == 'a':
        start, finish = Position(left, top), Position(right, top)
    elif segment == 'b':
        start, finish = Position(right, top), Position(right, middle)
    elif segment == 'c':
        start, finish = Position(right, middle), Position(right, bottom)
    elif segment == 'd':
        start, finish = Position(left, bottom), Position(right, bottom)
    elif segment == 'e':
        start, finish = Position(left, middle), Position(left, bottom)
    elif segment == 'f':
        start, finish = Position(left, top), Position(left, middle)
    elif segment == 'g':
        start, finish = Position(left, middle), Position(right, middle)
    else:
        raise ValueError('Invalid segment {}'.format(segment))
    start_px = pixel_scale(start)
    size_px = pixel_scale(Position(finish.x - start.x + line_width.x, finish.y - start.y + line_width.y))
    box = Rect(start_px, size_px)
    window.fill(color, box)


def init_window():
    app_id = 'diegorodriguezv.pong.1'  # arbitrary string
    # show the correct taskbar icon in windows
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
    # os.environ['SDL_VIDEO_CENTERED'] = '1'
    position = 410, 30
    os.environ['SDL_VIDEO_WINDOW_POS'] = str(position[0]) + "," + str(position[1])
    pre_init(44100, -16, 1)
    pygame.init()
    pygame.display.set_icon(pygame.image.load('img/icon.png'))
    result_window = pygame.display.set_mode((1500, 1000))
    pygame.display.set_caption('Pong')
    result_window.fill(ColorPalette.Background)
    return result_window


window = init_window()
win_w, win_h = window.get_size()
text_surface = None
fps_font = pygame.font.SysFont('couriernew', 20)
big_font = pygame.font.SysFont('couriernew', 60)
hit_wall_sound = Sound(precompute(one_period_square_wave_samples, frequency=226, milliseconds=16))
hit_wall_sound.set_volume(.1)
hit_paddle_sound = Sound(precompute(one_period_square_wave_samples, frequency=459, milliseconds=96))
hit_paddle_sound.set_volume(.1)
goal_sound = Sound(precompute(one_period_square_wave_samples, frequency=490, milliseconds=257))
goal_sound.set_volume(.1)
field_size = Size(width=180, height=100)
left_paddle = Paddle(10)
right_paddle = Paddle(170)
ball = Ball()
ball.kick_off(None)
left_direction, right_direction = None, None
score = (0, 0)
KICKOFF = pygame.USEREVENT + 1
ready_to_kick_off = False
delaying_kick_off = False
kick_off_direction = None
showing_winner_screen = False
speed_multipliers = [("1/64 X", 1 / 64), ("1/32 X", 1 / 32), ("1/16 X", 1 / 16), ("1/8 X", 1 / 8), ("1/4 X", 1 / 4),
                     ("1/2 X", 1 / 2), ("1 X", 1), ("1.5 X", 3 / 2), ("2 X", 2), ("4 X", 4), ("8 X", 8)]
speed_multiplier_index = 6
constant_delta = 1 / 24 * 1000
delta = constant_delta
t0 = time.clock()
show_fps = False
show_limits = False
my_clock = pygame.time.Clock()
virtual_time = 0
time_accumulator = 0
frame_count = 0
interpolation = True
skipping = False
pause = False
alive = True
while alive:
    frame_time = my_clock.tick(120)
    max_skip_frame = 5
    overwhelmed = frame_time > max_skip_frame * delta
    if overwhelmed:
        pause = True
        skipping = True
    if skipping:
        if not overwhelmed:
            pause = False
            skipping = False
    for input_event in pygame.event.get():
        if input_event.type == QUIT:
            alive = False
            break
        elif input_event.type == KEYDOWN:
            if input_event.key == K_ESCAPE:
                alive = False
                break
            elif input_event.key == K_UP:
                right_direction = Direction.Up
            elif input_event.key == K_DOWN:
                right_direction = Direction.Down
            elif input_event.key == K_w:
                left_direction = Direction.Up
            elif input_event.key == K_s:
                left_direction = Direction.Down
            elif input_event.key == K_p:
                pause = not pause
                if pause:
                    message = "PAUSE"
                else:
                    message = None
            elif input_event.key == K_l:
                show_limits = not show_limits
            elif input_event.key == K_f:
                show_fps = not show_fps
            elif input_event.key == K_i:
                interpolation = not interpolation
            elif input_event.key == K_r:
                showing_winner_screen = False
                delaying_kick_off = True
                kick_off_direction = None
                virtual_time = 0
                score = (0, 0)
                window.fill(ColorPalette.Background)
                ball.speed = Vector(0, 0)
                ball.position = Position(5000, 50)  # hide ball
                left_paddle.position = Position(10, field_size.height / 2)
                right_paddle.position = Position(170, field_size.height / 2)
                pygame.time.set_timer(KICKOFF, 1000)
            elif input_event.key == K_z:
                if speed_multiplier_index > 0:
                    speed_multiplier_index -= 1
                display_message_duration("{}".format(speed_multipliers[speed_multiplier_index][0]))
            elif input_event.key == K_x:
                if speed_multiplier_index <= len(speed_multipliers) - 2:
                    speed_multiplier_index += 1
                display_message_duration("{}".format(speed_multipliers[speed_multiplier_index][0]))
        elif input_event.type == KEYUP:
            if input_event.key == K_UP:
                right_direction = None
            elif input_event.key == K_DOWN:
                right_direction = None
            elif input_event.key == K_w:
                left_direction = None
            elif input_event.key == K_s:
                left_direction = None
        elif input_event.type == KICKOFF:
            ready_to_kick_off = True
        elif input_event.type == ERASEMESSAGE:
            erase_message()
    # 'impossible ai' moves left paddle, with a little wiggle room to reduce shakiness
    if center(left_paddle.position.y, left_paddle.size.height) < center(ball.position.y, ball.size.height) - 2:
        left_direction = Direction.Down
    elif center(left_paddle.position.y, left_paddle.size.height) > center(ball.position.y, ball.size.height) + 2:
        left_direction = Direction.Up
    else:
        left_direction = None
    clear_field()
    ball.clear()
    left_paddle.clear()
    right_paddle.clear()
    if not pause:
        time_accumulator += frame_time * speed_multipliers[speed_multiplier_index][1]
        delta = constant_delta
        while time_accumulator >= delta:
            time_accumulator -= delta
            virtual_time += delta
            if showing_winner_screen:
                if ball.position.y <= 1.1:
                    ball.bounce(0)
                if ball.position.y + ball.size.height >= field_size.height - 1:
                    ball.bounce(0)
                if ball.position.x <= 1.1:
                    ball.bounce(90)
                if ball.position.x + ball.size.width >= field_size.width - 1:
                    ball.bounce(90)
            else:
                if ball.position.y <= 1.1:
                    ball.bounce(0)
                    hit_wall_sound.play()
                if ball.position.y + ball.size.height >= field_size.height - 1:
                    ball.bounce(0)
                    hit_wall_sound.play()
                if ball.collides(left_paddle):
                    ball.bounce(90)
                    hit_paddle_sound.play()
                if ball.collides(right_paddle):
                    angle = right_paddle.reflection_angle(ball)
                    print("angle={}".format(angle))
                    print(ball.speed, slope(ball.speed))
                    ball.bounce(angle)
                    print(ball.speed, slope(ball.speed))
                    hit_paddle_sound.play()
                if ball.position.x <= 1.1:
                    if not delaying_kick_off:
                        score = score[0], score[1] + 1
                        goal_sound.play()
                        delaying_kick_off = True
                        kick_off_direction = Direction.Left
                        pygame.time.set_timer(KICKOFF, 2000)
                        ball.speed = Vector(0, 0)
                        ball.position = Position(5000, 50)  # hide ball
                if ball.position.x + ball.size.width >= field_size.width - 1:
                    if not delaying_kick_off:
                        score = score[0] + 1, score[1]
                        goal_sound.play()
                        delaying_kick_off = True
                        kick_off_direction = Direction.Right
                        pygame.time.set_timer(KICKOFF, 2000)
                        ball.speed = Vector(0, 0)
                        ball.position = Position(5000, 50)  # hide ball
            if any(s == 11 for s in score):
                if not showing_winner_screen:
                    pygame.time.set_timer(KICKOFF, 0)
                    left_paddle.position = Position(5000, 50)
                    right_paddle.position = Position(5000, 50)
                    showing_winner_screen = True
                    ball.start_win_screen()
            if ready_to_kick_off:
                pygame.time.set_timer(KICKOFF, 0)
                ready_to_kick_off = False
                delaying_kick_off = False
                ball.kick_off(kick_off_direction)
                print(score)
            ball.update()
            left_paddle.move(left_direction)
            left_paddle.update()
            right_paddle.move(right_direction)
            right_paddle.update()
    # alpha is a value between 0 and 1 that represents the portion of delta that has passed since last update
    if interpolation:
        alpha = time_accumulator / constant_delta
    else:
        alpha = 1
    frame_count += 1
    draw_field()
    ball.draw(alpha)
    left_paddle.draw(alpha)
    right_paddle.draw(alpha)
    pygame.display.update()

    # todo: bug: ball slides over bottom (when kicked off precisely), the hit sound repeats all the way
    # todo: bug: when the ball collides with the paddle diagonally ball bounces back and forth around the paddle
    # todo: make tests for the bugs (kick_off parameters + paddle positions)
    # todo: boolean flags should be renamed is_whatever
