
<h1>Classic Monitor ESP32 MQTT publisher</h1>



<p>
Classic Monitor MQTT will read data from your classic over Modbus and publish it to a MQTT broker. It is a Read Only Program, it does not write to the Classic.

The software is provided "AS IS", WITHOUT WARRANTY OF ANY KIND, express or implied.
Classic Monitor is NOT a product of Midnite solar, nor do they support this application!
</p>

<p align="center">
  <img src="./docs/images_en/ESP32.png" width="640"/>
</p>
<p>
Please refer to the IotWebConf for the ESP32 Wifi setup: https://github.com/prampec/IotWebConf.
</p>
<p align="center">
  <img src="./pictures/SetupPage.PNG" width="640"/>
  
  The AP Password is initially set to ClassicMQTT and must be changed to be able to apply the changes (can reuse ClassicMQTT)
  Once the app is in Station mode, the setup page can be accessed with admin:AP Password
</p>
<p>
the binary for the ESP32 is available here https://github.com/graham22/ClassicMQTT/releases.
</p>

<p>
<h3>Classic Monitor MQTT Subscriber app for Android is available here.</h3>
</p>

<p>
https://www.dropbox.com/sh/z3kzddtj17vk9t2/AACFwHN0phXpMuD9T3-Kvt8Ta?dl=0
</p>

<p>
Online help for the Android app: http://graham22.github.io/Classic/classicmonitor/help_en.html
</p>

Development environment used is Visual Studio CODE with the PlatformIO extension

<p>
<h3>Blynk app. </h3>
</p>

<p>
http://docs.blynk.cc/
</p>

<p>
You can scan this QR code from the Blynk App and you’ll get a ready-to-test project for the ESP32. Just put your Auth Token into the Wifi setup page when you configure the ESP32. 
</p>
<img src="./docs/images_en/Blynk_QR.png" width="640"/>
<img src="./docs/images_en/Blynk.png" width="640"/>

The Blynk app is available for Android and IOS (https://www.blynk.cc/)
<img src="./docs/images_en/IPAD.png" width="640"/>


## License
```

 Copyright (c) 2019

  Licensed under the Apache License, Version 2.0 (the "License");
  you may not use this file except in compliance with the License.
  You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing, software
  distributed under the License is distributed on an "AS IS" BASIS,
  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
  See the License for the specific language governing permissions and
  limitations under the License.

```


Release notes:

-----------------

version 1.2

<ul>
<li>Updated to use IOTWebConf and AsyncMQTTClient</li>
</ul>

-----------------
version 1.0.0

<ul>
<li>Initial Release</li>
</ul>

-----------------

