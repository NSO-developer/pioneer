<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:netconf10="urn:ietf:params:xml:ns:netconf:base:1.0"
                xmlns:netconf11="urn:ietf:params:xml:ns:netconf:base:1.1">
  <xsl:output method="xml" indent="yes"/>

  <xsl:template match="/">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply">
    <config xmlns="http://tail-f.com/ns/config/1.0">
      <devices xmlns="http://tail-f.com/ns/ncs">
        <device>
          <name><xsl:value-of select="$device_name"/></name>
          <config>
            <xsl:apply-templates/>
          </config>
        </device>
      </devices>
    </config>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply/netconf10:data">
    <xsl:copy-of select="*"/>
  </xsl:template>

  <xsl:template match="*">
    <xsl:message terminate="yes">
      WARNING: Unmatched element: <xsl:value-of select="name()"/>
    </xsl:message>
    <xsl:apply-templates/>
  </xsl:template>
</xsl:stylesheet>
