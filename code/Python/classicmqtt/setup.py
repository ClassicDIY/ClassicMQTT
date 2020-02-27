from setuptools import setup, find_packages 

with open('requirements.txt') as f: 
	requirements = f.readlines() 

long_description = 'The Python implementation of the ClassicMQTT' 

setup( 
		name ='classic_mqtt', 
		version ='1.0.0', 
		author ='Matt Sargent', 
		author_email ='matthew.c.sargent@gmail.com', 
		url ='https://github.com/mcsarge', 
		description ='ClassicMQTT implementation in Python', 
		long_description = long_description, 
		long_description_content_type ="text/markdown", 
		license ='MIT', 
		packages = find_packages(), 
		entry_points ={ 
			'console_scripts': [ 
				'classic_mqtt = vlassic_mqtt.classic_mqtt:run'
			]
		},
		classifiers =( 
			"Programming Language :: Python :: 3", 
			"License :: OSI Approved :: MIT License", 
			"Operating System :: OS Independent", 
		), 
		keywords ='classic mqtt classic_mqtt', 
		install_requires = requirements, 
		zip_safe = False
) 
