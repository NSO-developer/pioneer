<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:netconf10="urn:ietf:params:xml:ns:netconf:base:1.0"
                xmlns:netconf11="urn:ietf:params:xml:ns:netconf:base:1.1"
                xmlns:monitoring="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring">
  <xsl:output method="text"/>

  <xsl:template match="/">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply/monitoring:data">
    <xsl:value-of select="."/>
  </xsl:template>

  <xsl:template match="/netconf10:rpc-reply/netconf10:rpc-error">
    <xsl:text>ERROR</xsl:text>
  </xsl:template>
  
  <xsl:template match="*">
    <xsl:message terminate="yes">
      WARNING: Unmatched element: <xsl:value-of select="name()"/>
    </xsl:message>
    <xsl:apply-templates/>
  </xsl:template>
  <xsl:template match="text( )|@*"/>
</xsl:stylesheet>
