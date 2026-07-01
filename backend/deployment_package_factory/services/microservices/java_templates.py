from __future__ import annotations

from pathlib import PurePosixPath

from deployment_package_factory.services.microservices.templates_common import TemplateFile


def render_java_files(context: dict[str, object]) -> list[TemplateFile]:
    return [
        TemplateFile(PurePosixPath("pom.xml"), java_pom(context)),
        TemplateFile(PurePosixPath("src/main/resources/application.yml"), java_application_yml(context)),
        TemplateFile(PurePosixPath("src/main/java/com/example/domain/DemoItem.java"), domain_model()),
        TemplateFile(PurePosixPath("src/main/java/com/example/application/DemoService.java"), application_service()),
        TemplateFile(PurePosixPath("src/main/java/com/example/interfaces/HealthController.java"), controller()),
        TemplateFile(PurePosixPath("src/main/java/com/example/Application.java"), main_class()),
    ]


def java_required_files() -> list[str]:
    return [
        "pom.xml",
        "src/main/java/com/example/domain/DemoItem.java",
        "src/main/java/com/example/application/DemoService.java",
        "src/main/java/com/example/interfaces/HealthController.java",
        "src/main/java/com/example/Application.java",
    ]


def java_pom(context: dict[str, object]) -> str:
    return f"""<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.example</groupId>
  <artifactId>{context['service_key']}</artifactId>
  <version>0.1.0</version>
  <properties>
    <java.version>17</java.version>
    <maven.compiler.release>${{java.version}}</maven.compiler.release>
    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
    <spring-boot.version>3.3.0</spring-boot.version>
  </properties>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
      <version>${{spring-boot.version}}</version>
    </dependency>
    <dependency>
      <groupId>com.alibaba.cloud</groupId>
      <artifactId>spring-cloud-starter-alibaba-nacos-discovery</artifactId>
      <version>2023.0.1.0</version>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-data-jpa</artifactId>
      <version>${{spring-boot.version}}</version>
    </dependency>
  </dependencies>
  <build>
    <plugins>
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-compiler-plugin</artifactId>
        <version>3.13.0</version>
        <configuration>
          <release>${{java.version}}</release>
        </configuration>
      </plugin>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
        <version>${{spring-boot.version}}</version>
      </plugin>
    </plugins>
  </build>
</project>
"""


def java_application_yml(context: dict[str, object]) -> str:
    return f"""server:
  port: {context['port']}
spring:
  application:
    name: {context['service_key']}
  cloud:
    nacos:
      discovery:
        server-addr: ${{NACOS_ENDPOINT:localhost:8848}}
"""


def domain_model() -> str:
    return "package com.example.domain;\n\npublic record DemoItem(String name, String normalizedName) {}\n"


def application_service() -> str:
    return """package com.example.application;

import com.example.domain.DemoItem;
import org.springframework.stereotype.Service;

@Service
public class DemoService {
  public DemoItem create(String name) {
    return new DemoItem(name, name.toLowerCase().replaceAll("[^a-z0-9-]+", "-"));
  }
}
"""


def controller() -> str:
    return """package com.example.interfaces;

import com.example.application.DemoService;
import org.springframework.web.bind.annotation.*;

@RestController
public class HealthController {
  private final DemoService demoService;

  public HealthController(DemoService demoService) {
    this.demoService = demoService;
  }

  @GetMapping("/health")
  public Object health() {
    return java.util.Map.of("status", "ok");
  }

  @PostMapping("/api/v1/items/{name}")
  public Object create(@PathVariable String name) {
    return demoService.create(name);
  }
}
"""


def main_class() -> str:
    return """package com.example;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class Application {
  public static void main(String[] args) {
    SpringApplication.run(Application.class, args);
  }
}
"""
