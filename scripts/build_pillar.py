#Description


#Libraries
import os
import string
import sys
import logging
import random
import re
import yaml

#Logging config
logging.basicConfig(filename="/var/log/heat-deployments/build_pillar_script.log", level=logging.DEBUG)

#Argument checks
if len(sys.argv) != 13: 
	logging.error("Invalid number of arguments. Check the invocation in the heat template.")
	exit(1)

#Constant variables
SCRIPT_NAME = sys.argv[0]
LEFT_NETWORKS = sys.argv[1]
DHCP_POOL_CIDR = sys.argv[2]
GROUP_NAME = sys.argv[3]
PRIVATE_KEY = sys.argv[4]
LIST_OF_USERS = sys.argv[5]
CONCENTRATOR_PORT_ID = sys.argv[6]
DEPLOY_ACTION = sys.argv[7]
USER_PASSWDS_OUTPUT_FILE = sys.argv[8]
NEUTRON_COMMAND_OUTPUT_FILE = sys.argv[9]
PILLAR_FILE_PATH = sys.argv[10]
ROUTER_UUID = sys.argv[11]
GROUP_NAME_OUTPUT_FILE = sys.argv[12]


#Methods

#This method is called if the user secifies the "delete:"
#prefix when entering the user list on a stack update
def delete_users(user_list, pillar_file_dict):
	print "You are about to delete: ",user_list
	for user in user_list:
		try:
			logging.info("Deleting user " + user)
			del pillar_file_dict['ipsecconf']['users'][user]
		except KeyError:
			logging.warning("Cloud not find %s in the pillar file" % user)
			print "Cloud not find %s in the pillar file" % user
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write( yaml.dump(pillar_file_dict, default_flow_style=False))

	#Clearing the users/passwords from the heat output file.
	with open(USER_PASSWDS_OUTPUT_FILE, 'w') as outfile:
		outfile.write("The users and passwords are no longer available!")


#This method is called if the user specifies a list
#of users on a stack update.
def add_users(user_list, pillar_file_dict):
	if '' in user_list:
		logging.info("User list is empty..leaving it alone")
		return
	print "You are about to add: ",user_list

	#Clearing heat output file
	with open(USER_PASSWDS_OUTPUT_FILE, 'w') as outfile:
		logging.info("Clearing the old users that could have been left over in the output file..preparing to add users.")
		outfile.write("The information for the newly created users are: ")

	#Do things here to pillar_file_dict to add users
	for user in user_list:
		logging.info("Adding user " + user)
		password = password_gen()
		pillar_file_dict['ipsecconf']['users'][user] = password

		#Writing to heat output file
		with open(USER_PASSWDS_OUTPUT_FILE, 'a') as outfile:
			logging.info("Writing newly added users to the heat software config output file")
			outfile.write("{%(user)s: %(password)s}" % {'user':user,'password':password})

	#Writing the newly updated pillar file dict to the pillar file
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write( yaml.dump(pillar_file_dict, default_flow_style=False))

#This method is called if the user specfies the "updatepw:"
#prefix when entering the user list on a stack update
def updatepw(user_list, pillar_file_dict):
	print "You are about to update the password for: ",user_list
	logging.info("You are about to update the password for user(s): %s" % user_list)

	#Clearing the heat output file
	with open(USER_PASSWDS_OUTPUT_FILE, 'w') as outfile:
		outfile.write("The updated passwords are: ")

	for user in user_list:
		password = password_gen()

		#Checking to see if user exists
		if user in pillar_file_dict['ipsecconf']['users'].keys():
			logging.info("Updated password for %s" % user)
			pillar_file_dict['ipsecconf']['users'][user] = password
			#Writing the updated passwords to the heat output file.
			with open(USER_PASSWDS_OUTPUT_FILE, 'a') as outfile:
				outfile.write("{%(user)s: %(password)s}" % {'user':user,'password':password})
		else:
			logging.warning("User %s does not exist" % user)

	#Writing the newly updated pilar file dict to the pillar file
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write( yaml.dump(pillar_file_dict, default_flow_style=False))

#This method is called when the user specifies the "delete:"
#prefix when entering the list of left networks on a stack update
def delete_networks(network_list, pillar_file_dict):
	print "You are about to delete: ", network_list
	tmp_networks_list = pillar_file_dict['ipsecconf']['left_networks'].split(",")
	for network in network_list:
		try:
			tmp_networks_list.remove(network)
			logging.info("Deleting " + network)
		except ValueError:
			logging.warning("Could not find %s network in the pillar file" % network)
			print "Cloud not find %s network in the pillar file" % network
	pillar_file_dict['ipsecconf']['left_networks'] = ",".join(tmp_networks_list)
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write( yaml.dump(pillar_file_dict, default_flow_style=False))

#This method is called when the user specifies left
#networks on a stack update
def add_networks(networks_list, pillar_file_dict):
	print "You are about to add networks: ", networks_list
	if '' in networks_list:
		logging.info("Network list is empty..leaving it alone")
		return
	tmp_networks_list = pillar_file_dict['ipsecconf']['left_networks'].split(",")
	for network in networks_list:
		if network not in tmp_networks_list:
			tmp_networks_list.append(network)
			logging.info("Adding " + network)
		else:
			logging.info("Network %s is already in the pillar file.")
	#Writing new networks to the pillar_file_dict
	pillar_file_dict['ipsecconf']['left_networks'] = ",".join(tmp_networks_list)
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write( yaml.dump(pillar_file_dict, default_flow_style=False))

#This method is called on stack creation. 
#It generates the salt pillar file.
def create_pillar(user_list, networks_list):
	print "You are about to create the pillar file"
	#The VPN group name, which is the GROUP_NAME prefix plus the first 11
	#characters of the neutron router UUID
	vpn_group = GROUP_NAME + "-" + ROUTER_UUID[0:11]
	pillar_file_dict = {
		'ipsecconf': {
			'dhcp_pool_cidr': DHCP_POOL_CIDR,
			'private_key': PRIVATE_KEY,
			'group_name': vpn_group,
			'left_networks': ','.join(networks_list),
			'users': {}
		}
	}
	for user in user_list:
		logging.info("Adding user " + user)
		password = password_gen()
		pillar_file_dict['ipsecconf']['users'][user] = password
		with open(USER_PASSWDS_OUTPUT_FILE, 'a') as outfile:
			outfile.write("{%(user)s: %(password)s}" % {'user': user, 'password': password})
	with open(PILLAR_FILE_PATH, 'w+') as outfile:
		outfile.write(yaml.dump(pillar_file_dict, default_flow_style=False))

	#Write out VPN group name to heat output file
	with open(GROUP_NAME_OUTPUT_FILE, 'w') as outfile:
		outfile.write(vpn_group)

def clear_passwords():
	with open(USER_PASSWDS_OUTPUT_FILE, 'w+') as outfile:
		logging.info("Clearing the user/passwords from the stack output..")
		outfile.write("The passwords have been cleared successfully")
		exit(0)

def load_pillar():
	if os.path.isfile(PILLAR_FILE_PATH):
		stream = open(PILLAR_FILE_PATH, 'r')
		return yaml.load(stream)
	else:
		logging.info("Pillar file does not exist, creating one..")

def password_gen():
	return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))


#This method builds the string necessary for a nuetron port-update. It is
#then written to it's appropriate heat output file. 
def build_neutron_port_command():
	#Loading the pillar file
	pillar_file_dict = load_pillar()
	command = "neutron port-update " + CONCENTRATOR_PORT_ID + " --allowed-address-pairs list=true type=dict ip_address=" + DHCP_POOL_CIDR + " "
	print command

	#Writing first part of the command to the heat output file
	with open(NEUTRON_COMMAND_OUTPUT_FILE, 'w') as outfile:
		logging.info("Writing the first part of the neutron command into heat output file..")
		outfile.write(command)

	tmp_network_list = pillar_file_dict['ipsecconf']['left_networks'].split(",")
	for network in tmp_network_list:
		with open(NEUTRON_COMMAND_OUTPUT_FILE, 'a') as outfile:
			logging.info("Adding %s network into neutron port-update heat output file..")
			outfile.write("ip_address=" + network + " ")

#Main Method
def main():

	#---Variables. 

	#Converting comma delimited strings into lists
	left_networks_list = LEFT_NETWORKS.split(",")
	list_of_users_list = LIST_OF_USERS.split(",")

	#Trim leading or trailing whitespace
	for i in range(len(left_networks_list)):
		left_networks_list[i] = left_networks_list[i].strip()
	for i in range(len(list_of_users_list)):
		list_of_users_list[i] = list_of_users_list[i].strip()

	##Used to determine if the user is going to delete a network or vpn user.
	if "delete:" in list_of_users_list[0]:
		is_delete_users = True
		list_of_users_list[0] = re.sub('delete:\s*', '', list_of_users_list[0])
	else:
		is_delete_users = False
	if "delete:" in left_networks_list[0]:
		is_delete_networks = True
		left_networks_list[0] = re.sub('delete:\s*', '', left_networks_list[0])
	else:
		is_delete_networks = False

	##Used to determine if user is updating the stack
	if DEPLOY_ACTION == 'UPDATE':
		is_update = True
	else:
		is_update = False

	##Used to determine if user is updating VPN user passwords
	if "updatepw:" in list_of_users_list[0]:
		is_updatepw = True
		list_of_users_list[0] = re.sub('updatepw:\s*', '', list_of_users_list[0])

	else:
		is_updatepw = False

	##Used to determine if user is clearing passwords from stack output
	if "clear passwords" in list_of_users_list[0]:
		is_clear = True
	else:
		is_clear = False



	#---Logic to carry out the functions specified by the user

	##Load pillar file if it exists
	pillar_file_dict = load_pillar()

	##Build the pillar file on stack creation
	if DEPLOY_ACTION == 'CREATE' and not is_delete_users and not is_delete_networks:
		create_pillar(list_of_users_list, left_networks_list)

	##Clear users and passwords from output if user specifies
	if is_clear:
		clear_passwords()

	##Delete user or network when specified
	if is_delete_users:
		delete_users(list_of_users_list, pillar_file_dict)
	if is_delete_networks:
		delete_networks(left_networks_list, pillar_file_dict)

	##Add user or network when specified
	if is_update and not is_delete_networks:
		add_networks(left_networks_list, pillar_file_dict)
	if is_update and not is_delete_users and not is_updatepw:
		add_users(list_of_users_list, pillar_file_dict)

	##Update passwords of users when specified
	if is_updatepw and is_update:
		updatepw(list_of_users_list, pillar_file_dict)

	#Loading (re)built pillar file
	build_neutron_port_command()

#Calling main
main()