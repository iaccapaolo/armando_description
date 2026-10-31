#!/usr/bin/env python3
"""

Il nodo:
  1. legge la posizione attuale dei giunti da /joint_states (una sola volta,
     per partire da dove si trova il braccio ed evitare salti);
  2. legge un tasto alla volta dal terminale;
  3. aggiorna la posizione desiderata del giunto corrispondente;
  4. pubblica una JointTrajectory con un solo punto sul topic del
     joint_trajectory_controller (lo stesso usato a mano con `ros2 topic pub`).

Uso:
  ros2 run armando_description armando_teleop.py
  
"""

import os
import select
import sys
import termios
import tty

import rclpy
from rclpy.node import Node
from builtin_interfaces.msg import Duration
from sensor_msgs.msg import JointState
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint


# --- Parametri ---------------------------------------------------------------
JOINTS = ['j0', 'j1', 'j2', 'j3']          # nomi dei giunti come nell'URDF
LOWER, UPPER = -3.14, 3.14                  # limiti dei giunti dall'URDF [rad]
STEP = 0.05                                 # incremento per ogni tasto [rad]
MOVE_TIME = 0.2                             # tempo per raggiungere il punto [s]
                                            # -> velocità = STEP / MOVE_TIME = 0.25 rad/s
TRAJ_TOPIC = '/joint_trajectory_controller/joint_trajectory'

# tasto -> (indice del giunto, verso)
KEYMAP = {
    'q': (0, +1), 'a': (0, -1),
    'w': (1, +1), 's': (1, -1),
    'e': (2, +1), 'd': (2, -1),
    'r': (3, +1), 'f': (3, -1),
}

HELP = """
---------------------------------------------
 Armando - teleoperazione giunti da tastiera
---------------------------------------------
   j0:  q (+)   a (-)
   j1:  w (+)   s (-)
   j2:  e (+)   d (-)
   j3:  r (+)   f (-)

   h : home (tutti i giunti a 0)
   x : esci        (anche Ctrl+C)

 Passo: %.2f rad per tasto
---------------------------------------------
""" % STEP


class ArmTeleop(Node):

    def __init__(self):
        super().__init__('armando_teleop')
        self.pub = self.create_publisher(JointTrajectory, TRAJ_TOPIC, 10)
        self.sub = self.create_subscription(
            JointState, '/joint_states', self.joint_state_cb, 10)
        # posizione desiderata dei 4 giunti; None finché non arriva /joint_states
        self.target = None

    def joint_state_cb(self, msg):
        """Copia la posizione reale dei giunti, solo la prima volta."""
        if self.target is not None:
            return
        # l'ordine dei nomi in /joint_states non è garantito: cerco per nome
        positions = dict(zip(msg.name, msg.position))
        if all(j in positions for j in JOINTS):
            self.target = [positions[j] for j in JOINTS]
            self.get_logger().info(
                'Posizione iniziale: ' + self.format_target())

    def move(self, idx, direction):
        """Incrementa un giunto di un passo, restando nei limiti."""
        new = self.target[idx] + direction * STEP
        self.target[idx] = min(max(new, LOWER), UPPER)

    def home(self):
        self.target = [0.0] * len(JOINTS)

    def publish_target(self):
        msg = JointTrajectory()
        msg.joint_names = JOINTS
        point = JointTrajectoryPoint()
        point.positions = list(self.target)
        point.time_from_start = Duration(sec=0, nanosec=int(MOVE_TIME * 1e9))
        msg.points = [point]
        self.pub.publish(msg)

    def format_target(self):
        return '  '.join(f'{j}={p:+.2f}' for j, p in zip(JOINTS, self.target))


def read_key(timeout):
    """Restituisce un carattere se premuto entro `timeout` secondi, altrimenti None.

    select() evita di restare bloccati in attesa: così il ciclo principale
    continua a girare e ROS a ricevere messaggi anche senza tasti premuti.
    os.read() legge direttamente dal file descriptor, senza il buffer di
    sys.stdin che altrimenti potrebbe "nascondere" i caratteri a select().
    """
    ready, _, _ = select.select([sys.stdin], [], [], timeout)
    if not ready:
        return None
    return os.read(sys.stdin.fileno(), 1).decode(errors='ignore')


def main(args=None):
    if not sys.stdin.isatty():
        print('Questo nodo legge la tastiera: lancialo con `ros2 run` '
              'in un terminale, non da un launch file.')
        return

    rclpy.init(args=args)
    node = ArmTeleop()

    # salvo le impostazioni del terminale per ripristinarle all'uscita
    old_settings = termios.tcgetattr(sys.stdin)

    try:
        print(HELP)

        # 1) aspetto la posizione attuale del braccio
        node.get_logger().info('In attesa di /joint_states...')
        while rclpy.ok() and node.target is None:
            rclpy.spin_once(node, timeout_sec=0.1)

        # 2) modalità cbreak: un tasto alla volta, senza Invio e senza eco;
        #    Ctrl+C continua a funzionare
        tty.setcbreak(sys.stdin.fileno())

        # 3) ciclo principale
        while rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.0)
            key = read_key(timeout=0.05)
            if key is None:
                continue
            key = key.lower()

            if key in KEYMAP:
                node.move(*KEYMAP[key])
            elif key == 'h':
                node.home()
            elif key == 'x':
                break
            else:
                continue            # tasto non mappato: ignoro

            node.publish_target()
            print('\r' + node.format_target() + '   ', end='', flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        # rimetto il terminale com'era, altrimenti resta senza eco
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        print('\nUscita.')
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == '__main__':
    main()