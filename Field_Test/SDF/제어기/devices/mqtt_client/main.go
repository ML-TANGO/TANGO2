package main

import (
	"os"

	"gitlab.suredatalab.kr/sdlmicro/middleware/log"

	"gitlab.suredatalab.kr/beymons/common/mqtt"
)

var c = &mqtt.MqttClient{}

func main() {
	// 환경변수 확인
	c.Endpoint = getenvDefault("MQTT_ENDPOINT", "mqtt://localhost:1883")
	c.Topic = getenvDefault("MQTT_TOPIC", "+/+/_upstream/+")
	c.ClientId = getenvDefault("MQTT_CLIENT_ID", "beymons-device-server")
	rootCAFile := os.Getenv("MQTT_ROOT_CA_FILE")
	certFile := getenvDefault("MQTT_CERT_FILE", "server.cert.pem")
	privateKeyFile := getenvDefault("MQTT_PRIVATE_KEY_FILE", "server.private.key")
	insecure := false
	if os.Getenv("MQTT_INSECURE") == "yes" {
		insecure = true
	}

	log.Infof("Endpoint: %s", c.Endpoint)
	log.Infof("topic: %s", c.Topic)
	log.Infof("client ID: %s", c.ClientId)

	// MQTT Client 초기화
	log.Infof("new TLS config for MQTT Client")
	if err := c.SetTLSConfig(rootCAFile, certFile, privateKeyFile, insecure); err != nil {
		log.Fatal("Failed to load cert file", err.Error())
	}

	ch := make(chan os.Signal, 1)
	log.Infof("new MQTT client")
	if err := c.Connect(messageHandler); err != nil {
		log.Fatal("Failed to connect MQTT broker:", err.Error())
	}

	<-ch
	c.Client().Disconnect(250)
}

func getenvDefault(key, defaultValue string) string {
	value := os.Getenv(key)
	if len(value) == 0 {
		return defaultValue
	}
	return value
}
