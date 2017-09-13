#!/bin/env/python
"""Pong game: """
import math
import os
import random
import time
from array import array
from collections import namedtuple

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


Game = namedtuple('Game', 'width height')
Position = namedtuple('Position', 'x y')
Vector = namedtuple('Vector', 'x y')
Size = namedtuple('Size', 'width height')


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
    Green = (0, 255, 0)


class ColorPalette(Color):
    Paddle = Color.DarkGray
    Score = Color.LightGray
    Ball = Color.White
    HalfLine = Color.White
    Background = Color.Black


def pixel_scale(pos):
    x, y = pos
    w, h = window.get_size()
    return Position(int(x / game.width * w), int(y / game.height * h))


class Sprite:
    def __init__(self):
        self.position = Position(0, 0)
        self.size = Size(1, 1)
        self.speed = Vector(0, 0)
        self.min_speed = 0
        self.max_speed = 1
        self.color = ColorPalette.Green

    def update(self):
        self.clear()
        new_position = Position(
            self.position.x + self.speed.x * delta,
            self.position.y + self.speed.y * delta)
        self.position = new_position

    def draw(self):
        x, y = pixel_scale(self.position)
        w, h = pixel_scale(self.size)
        # window.fill() won't work in the edges
        pygame.draw.rect(window, self.color, (x, y, w, h))

    def clear(self):
        x, y = pixel_scale(self.position)
        w, h = pixel_scale(self.size)
        # window.fill() won't work in the edges
        pygame.draw.rect(window, ColorPalette.Background, (x, y, w, h))

    def collides(self, sprite):
        rect1 = Rect(self.position.x, self.position.y, self.size.width, self.size.height)
        rect2 = Rect(sprite.position.x, sprite.position.y, sprite.size.width, sprite.size.height)
        return rect1.colliderect(rect2)

    def bounce(self, angle):
        if angle == 0:
            self.speed = Vector(self.speed.x, -self.speed.y)
        elif angle == 90:
            self.speed = Vector(-self.speed.x, self.speed.y)
            # todo: different angle in head and tail
            # else:
            #     self.speed = Vector(self.speed.x * math.sin(math.radians(angle)),
            #                         -self.speed.y * math.cos(math.radians(angle)))


def center(target, size):
    return target - size / 2


class Paddle(Sprite):
    def __init__(self, x):
        super().__init__()
        self.size = Size(1, 5)
        self.position = Position(x, center(game.height / 2, self.size.height))
        self.min_speed = 6 / 100
        self.color = ColorPalette.Paddle

    def move(self, input_direction):
        if input_direction == Direction.Up:
            self.speed = Vector(0, -self.min_speed)
        elif input_direction == Direction.Down:
            self.speed = Vector(0, self.min_speed)
        else:
            self.speed = Vector(0, 0)


class Ball(Sprite):
    def __init__(self):
        super().__init__()
        self.size = Size(2, 2)
        self.position = Position(center(game.width / 2, self.size.width), center(game.height / 2, self.size.height))
        self.min_speed = 4 / 100
        self.color = ColorPalette.Ball

    def kick_off(self, direction):
        self.position = Position(center(game.width / 2, self.size.width),
                                 random.random() * game.height)
        # self.position = Position(center(game.width / 2, self.size.width), center(game.height / 2, self.size.height))
        if direction == Direction.Left:
            self.speed = Vector(-self.min_speed, (1 - 2 * random.random()) * self.min_speed)
        if direction == Direction.Right:
            self.speed = Vector(self.min_speed, (1 - 2 * random.random()) * self.min_speed)


def clear_field():
    clear_half_line()
    clear_score()
    clear_fps()


def draw_field():
    clear_field()
    draw_half_line()
    draw_score()
    draw_fps()
    draw_limits()


def draw_limits():
    corners = [(0, 0), (game.width, 0), (game.width, game.height), (0, game.height)]
    # corners = [(1, 1), (game.width - 1, 1), (game.width - 1, game.height - 1), (1, game.height - 1)]
    corners.append(corners[0])
    for corner in range(len(corners) - 1):
        start = pixel_scale(corners[corner])
        end = pixel_scale(corners[corner + 1])
        pygame.draw.line(window, ColorPalette.Score, start, end, 1)


def draw_fps():
    global font
    global text_surface
    elapsed = time.clock() - t0
    if elapsed == 0:
        fps = 0.0
    else:
        fps = frame_count / elapsed
    text_surface = font.render('FPS: {:04.2f} recent:{:04.2f}'.format(fps, my_clock.get_fps()), True, Color.Green)
    window.blit(text_surface, (0, 0))


def clear_fps():
    if text_surface is not None:
        window.fill(ColorPalette.Background, text_surface.get_rect())


def draw_half_line():
    segments = 30
    segment_length = game.height / segments
    for segment in range(segments):
        start = pixel_scale((game.width / 2, segment_length * segment))
        end = pixel_scale((game.width / 2, segment_length * segment + (3 / 4 * segment_length)))
        pygame.draw.line(window, ColorPalette.HalfLine, start, end, 2)


def clear_half_line():
    start = pixel_scale((game.width / 2, 0))
    end = pixel_scale((game.width / 2, game.height))
    pygame.draw.line(window, ColorPalette.Background, start, end, 2)


def draw_score():
    left, right = score
    draw_number(left, Position(50, 10), Size(8, 10))
    draw_number(right, Position(130, 10), Size(8, 10))


def clear_score():
    left, right = score
    clear_number(left, Position(50, 10), Size(8, 10))
    clear_number(right, Position(130, 10), Size(8, 10))


def draw_number(number, pos, size):
    digits = str(number)
    x_offset = 10
    next_draw_pos = pos
    for digit in digits:
        draw_digit(int(digit), next_draw_pos, size)
        next_draw_pos = Position(next_draw_pos.x + x_offset, next_draw_pos.y)


def clear_number(number, pos, size):
    digits = str(number)
    x_offset = 10
    next_draw_pos = pos
    for digit in digits:
        clear_digit(int(digit), next_draw_pos, size)
        next_draw_pos = Position(next_draw_pos.x + x_offset, next_draw_pos.y)


def draw_digit(digit, pos, size):
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
        draw_segment(segment, pos, size)


def clear_digit(digit, pos, size):
    left = pos.x
    right = pos.x + size.width
    top = pos.y
    middle = pos.y + size.height * 0.4
    bottom = pos.y + size.height
    horiz_lines = [
        (left, top), (right, top),
        (left, middle), (right, middle),
        (left, bottom), (right, bottom)]
    vert_lines = [(left, top), (left, bottom), (right, top), (right, bottom)]
    line_width = pixel_scale(Position(1, 1))
    h_it = iter(horiz_lines)
    for start in h_it:
        end = next(h_it)
        pygame.draw.line(window, ColorPalette.Background, pixel_scale(start), pixel_scale(end), line_width.y)
    v_it = iter(vert_lines)
    for start in v_it:
        end = next(v_it)
        pygame.draw.line(window, ColorPalette.Background, pixel_scale(start), pixel_scale(end), line_width.x)


def draw_segment(segment, pos, size):
    # 7 segments:
    #    a
    #    _
    #  f| |b
    #    g
    #    _
    #  e|_|c
    #    d
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
        start, finish = Position(left, bottom), Position(left, middle)
    elif segment == 'f':
        start, finish = Position(left, middle), Position(left, top)
    elif segment == 'g':
        start, finish = Position(left, middle), Position(right, middle)
    else:
        raise ValueError('Invalid segment {}'.format(segment))
    line_width = pixel_scale(Position(1, 1))
    if segment in 'adg':  # horizontal segment
        pygame.draw.line(window, ColorPalette.Score, pixel_scale(start), pixel_scale(finish), line_width.y)
    elif segment in 'bcef':  # vertical segement
        pygame.draw.line(window, ColorPalette.Score, pixel_scale(start), pixel_scale(finish), line_width.x)


def init_window():
    # os.environ['SDL_VIDEO_CENTERED'] = '1'
    position = 30, 30
    os.environ['SDL_VIDEO_WINDOW_POS'] = str(position[0]) + "," + str(position[1])
    pre_init(44100, -16, 1)
    pygame.init()
    window = pygame.display.set_mode((1500, 1000))
    pygame.display.set_caption('Pong')
    window.fill(ColorPalette.Background)
    return window


window = init_window()
win_w, win_h = window.get_size()
text_surface = None
font = pygame.font.SysFont('', 30)
hit_wall_sound = Sound(precompute(one_period_square_wave_samples, frequency=226, milliseconds=16))
hit_wall_sound.set_volume(.1)
hit_paddle_sound = Sound(precompute(one_period_square_wave_samples, frequency=459, milliseconds=96))
hit_paddle_sound.set_volume(.1)
goal_sound = Sound(precompute(one_period_square_wave_samples, frequency=490, milliseconds=257))
goal_sound.set_volume(.1)
game = Game(width=180, height=100)
left_paddle = Paddle(10)
right_paddle = Paddle(170)
ball = Ball()
ball.kick_off(Direction.Right)
left_direction, right_direction = None, None
score = (0, 0)
KICKOFF = pygame.USEREVENT + 1
ready_to_kick_off = False
delaying_kick_off = False
kick_off_direction = None
constant_delta = 1 / 120 * 1000
delta = constant_delta
t0 = time.clock()
my_clock = pygame.time.Clock()
virtual_time = 0
time_accumulator = 0
frame_count = 0
pause = False
alive = True
while alive:
    frame_time = my_clock.tick(60)
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
    if not pause:
        time_accumulator += frame_time
        while time_accumulator >= constant_delta:
            ball.update()
            left_paddle.move(left_direction)
            left_paddle.update()
            right_paddle.move(right_direction)
            right_paddle.update()
            time_accumulator -= delta
            virtual_time += delta
            if ball.position.y < 0:
                ball.bounce(0)
                hit_wall_sound.play()
            if ball.position.y + ball.size.height > game.height - 1:
                ball.bounce(0)
                hit_wall_sound.play()
            if ball.collides(left_paddle) or ball.collides(right_paddle):
                ball.bounce(90)
                hit_paddle_sound.play()
            if ball.position.x < 0:
                if not delaying_kick_off:
                    score = score[0], score[1] + 1
                    goal_sound.play()
                    delaying_kick_off = True
                    kick_off_direction = Direction.Left
                    pygame.time.set_timer(KICKOFF, 2000)
            if ball.position.x + ball.size.width > game.width - 1:
                if not delaying_kick_off:
                    score = score[0] + 1, score[1]
                    goal_sound.play()
                    delaying_kick_off = True
                    kick_off_direction = Direction.Right
                    pygame.time.set_timer(KICKOFF, 2000)
            if any(s == 11 for s in score):
                alive = False
                # todo: show winner screen
            if ready_to_kick_off:
                pygame.time.set_timer(KICKOFF, 0)
                ready_to_kick_off = False
                delaying_kick_off = False
                ball.kick_off(kick_off_direction)
                print(score)
    frame_count += 1
    # window.fill(ColorPalette.Background)
    draw_field()
    ball.draw()
    left_paddle.draw()
    right_paddle.draw()
    # pygame.display.flip()
    pygame.display.update()

    # todo: collisions and animation should be pixel perfect
    # todo: bug: ball slides over bottom (when kicked off precisely), the hit sound repeats all the way
    # todo animation should be as smooth as possible
    # todo: bug: paddles should have limits
