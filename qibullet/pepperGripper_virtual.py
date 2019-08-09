#!/usr/bin/env python
# coding: utf-8

import os
import pybullet
from qibullet.laser import *
from qibullet.camera import *
from qibullet.base_controller import *
from qibullet.robot_posture import PepperPosture
from qibullet.robot_virtual import RobotVirtual


class PepperGripperVirtual(RobotVirtual):
    """
    Class representing the virtual instance of a Pepper robot's gripper
    """
    ID_CAMERA_TOP = 0
    ID_CAMERA_BOTTOM = 1
    ID_CAMERA_DEPTH = 2
    FRAME_WORLD = 1
    FRAME_ROBOT = 2

    def __init__(self,gripper):
        """
        Constructor
        """
        urdf_path = "robot_data/pepper_1.7/pepper_"+gripper+".urdf"
        RobotVirtual.__init__(self,urdf_path)

        self.camera_top = None
        self.camera_bottom = None
        self.camera_depth = None
        self.motion_constraint = None
        # Default speed (in m/s) xy : 0.35, min : 0.1, max : 0.55
        self.linear_velocity = 0.35
        # Default speed (in rad/s) theta : 1.0, min : 0.3, max : 2.0
        self.angular_velocity = 1.0
        # Default acc (in m/s^2 xy : 0.3, min : 0.1, max : 0.55
        self.linear_acceleration = 0.3
        # Default acc (in rad/s^2 theta : 0.75, min : 0.1, max : 3.0
        self.angular_acceleration = 0.3

    def loadRobot(self, translation, quaternion, physicsClientId=0, useFixedBase=False):
        """
        Overloads @loadRobot from the @RobotVirtual class. Update max velocity
        for the fingers and thumbs, based on the hand joints. Add self
        collision exceptions (The biceps won't autocollide with the torso, the
        fingers and thumbs of a hand won't autocollide with the corresponding
        wrist). Add the cameras. Add motion constraint.
        """
        pybullet.setAdditionalSearchPath(
            os.path.dirname(os.path.realpath(__file__)),
            physicsClientId=physicsClientId)

        RobotVirtual.loadRobot(
            self,
            translation,
            quaternion,
            physicsClientId=physicsClientId,
            useFixedBase=useFixedBase)

        for name, link in self.link_dict.items():
            for wrist in ["r_wrist", "l_wrist"]:
                if wrist[0] + "finger" in name.lower() or\
                   wrist[0] + "thumb" in name.lower():
                    pybullet.setCollisionFilterPair(
                        self.robot_model,
                        self.robot_model,
                        self.link_dict[wrist].getIndex(),
                        link.getIndex(),
                        0,
                        physicsClientId=self.physics_client)

        for joint_name in list(self.joint_dict):
            if 'RFinger' in joint_name or 'RThumb' in joint_name:
                self.joint_dict[joint_name].setMaxVelocity(
                    self.joint_dict["RHand"].getMaxVelocity())
            elif 'LFinger' in joint_name or 'LThumb' in joint_name:
                self.joint_dict[joint_name].setMaxVelocity(
                    self.joint_dict["LHand"].getMaxVelocity())

        # self.motion_constraint = pybullet.createConstraint(
        #     parentBodyUniqueId=self.robot_model,
        #     parentLinkIndex=-1,
        #     childBodyUniqueId=-1,
        #     childLinkIndex=-1,
        #     jointType=pybullet.JOINT_FIXED,
        #     jointAxis=[0, 0, 0],
        #     parentFramePosition=[0, 0, 0.5],
        #     parentFrameOrientation=[0, 0, 0, 1],
        #     childFramePosition=[translation[0], translation[1], 0.5],
        #     childFrameOrientation=quaternion,
        #     physicsClientId=self.physics_client)

        self.base_controller = PepperBaseController(
            self.robot_model,
            [self.linear_velocity, self.angular_velocity],
            [self.linear_acceleration, self.angular_acceleration],
            self.motion_constraint,
            physicsClientId=self.physics_client)

    def moveTo(self, x, y, theta, frame=FRAME_ROBOT, speed=None, _async=False):
        """
        Move the robot in frame world or robot (FRAME_WORLD=1, FRAME_ROBOT=2).
        This method can be called synchonously or asynchronously. In the
        asynchronous mode, the function can be called when it's already
        launched, this will update the goal of the motion.

        Parameters:
            x - position of the goal on the x axis, in meters
            y - position of the goal on the y axis, in meters
            theta - orientation of the goal around the z axis, in radians
            frame - The frame in which the goal is expressed: FRAME_WORLD = 1,
            FRAME_ROBOT = 2
            speed - The desired linear velocity, in m/s
            _async - The method is launched in async mode if True, in synch
            mode if False (False by default)
        """
        if speed is not None:
            self.base_controller.setLinearVelocity(speed)

        self.base_controller.moveTo(x, y, theta, frame, _async=_async)

    def move(self, x, y, theta):
        """
        Apply a speed on the robot's base.

        Parameters:
            x - Speed on the x axis, in m/s
            y - Speed on the y axis, in m/s
            theta - Rotational speed around the z axis, in rad/s
        """
        self.base_controller.move(x, y, theta)


    def setAngles(self, joint_names, joint_values, percentage_speed):
        """
        Overloads @setAngles from the @RobotVirtual class. Handles the finger
        mimic behaviour.

        Parameters:
            joint_names - List of string (or string if only one joint)
            containing the name of the joints to be controlled
            joint_values - List of values (or value if only one joint)
            corresponding to the angles in radians to be applied
            percentage_speed - Percentage (or percentages) of the max speed to
            be used for the movement
        """
        try:
            if type(joint_names) is str:
                assert type(joint_values) is int or type(joint_values) is float
                names = [joint_names]
                values = [joint_values]
            else:
                assert type(joint_names) is type(joint_values) is list
                names = list(joint_names)
                values = list(joint_values)

            if isinstance(percentage_speed, list):
                speeds = list(percentage_speed)
            else:
                speeds = [percentage_speed]*len(names)

        except AssertionError:
            raise pybullet.error("Error in the parameters given to the\
                setAngles method")

        for hand in ["RHand", "LHand"]:
            for i in range(names.count(hand)):
                index = names.index(hand)
                value = values[index]
                speed = speeds[index]
                names.pop(index)
                values.pop(index)
                speeds.pop(index)
                finger_names, finger_values = self._mimicHand(hand, value)
                names.extend(finger_names)
                values.extend(finger_values)
                speeds.extend([speed]*len(finger_names))

        RobotVirtual.setAngles(
            self,
            names,
            values,
            speeds)

    def getAnglesPosition(self, joint_names):
        """
        Overloads @getAnglesPosition from the @RobotVirtual class. Handles the
        finger mimicked position for the hands (when getting the position of
        RHand or LHand, will return the hand's opening percentage).

        Parameters:
            joint_names - List of string (or string if only one joint)
            containing the name of the joints

        Returns:
            joint_positions - List of float (or float if only one joint)
            containing the joint's positions in radians
        """
        if type(joint_names) is str:
            names = [joint_names]
        else:
            names = list(joint_names)

        joint_positions = RobotVirtual.getAnglesPosition(self, names)

        for hand, finger in zip(
                ["RHand", "LHand"],
                ["RFinger11", "LFinger11"]):
            for i in range(names.count(hand)):
                index = names.index(hand)
                joint_positions[index] =\
                    RobotVirtual.getAnglesPosition(self, [finger]).pop() /\
                    (1/(self.joint_dict[finger].getUpperLimit() -
                        self.joint_dict[finger].getLowerLimit())) +\
                    self.joint_dict[finger].getLowerLimit()

        if len(joint_positions) == 1:
            return joint_positions.pop()
        else:
            return joint_position

    def isSelfColliding(self, link_names):
        """
        Specifies if a link is colliding with the rest of the virtual Pepper
        robot.

        Parameters:
            link_names - String or list of string containing the names of the
            links to be checked for self collision. WARNING: only the links
            with corresponding meshes should be used, otherwise the link cannot
            self collide

        Returns:
            self_colliding - Boolean, if True at least one of the links is self
            colliding
        """
        try:
            if type(link_names) is str:
                assert link_names in self.link_dict.keys()
                names = [link_names]
            else:
                assert set(link_names).issubset(self.link_dict.keys())
                names = list(link_names)

            for name in names:
                contact_tuple = pybullet.getContactPoints(
                    bodyA=self.robot_model,
                    bodyB=self.robot_model,
                    linkIndexA=self.link_dict[name].getIndex(),
                    physicsClientId=self.physics_client)
                contact_tuple += pybullet.getContactPoints(
                    bodyA=self.robot_model,
                    bodyB=self.robot_model,
                    linkIndexB=self.link_dict[name].getIndex(),
                    physicsClientId=self.physics_client)

                if len(contact_tuple) != 0:
                    return True

            return False

        except AssertionError:
            "Unauthorized link checking for self collisions"
            return False

    def _mimicHand(self, hand, value, multiplier=0.872665, offset=0):
        """
        Used to propagate a joint value on the fingers attached to the hand.
        The formula used to mimic a joint is the following (with a multiplier
        of 0.872665 and an offset of 0):

        finger_value = (hand_value * multiplier) + offset

        Parameters:
            hand - String, RHand or LHand
            value - the joint value to be propagated

        Returns:
            finger_names - Names of the finger to be controlled
            finger_values - Values of the fingers to be controlled
        """
        finger_names = list()
        finger_values = list()

        for joint_name in self.joint_dict.keys():
            if (hand[0] + "Finger") in joint_name or\
               (hand[0] + "Thumb") in joint_name:
                finger_names.append(joint_name)
                finger_values.append((value * multiplier) + offset)

        return finger_names, finger_values
