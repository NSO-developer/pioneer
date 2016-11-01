<xsl:stylesheet version="1.0"
                xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:netconf10="urn:ietf:params:xml:ns:netconf:base:1.0"
                xmlns:netconf11="urn:ietf:params:xml:ns:netconf:base:1.1"
                xmlns:ncstate="urn:ietf:params:xml:ns:yang:ietf-netconf-monitoring"
                xmlns:confdstate="http://tail-f.com/yang/confd-monitoring">
  <xsl:output method="text"/>

  <xsl:template match="/">
    <xsl:apply-templates/>
  </xsl:template>

  <xsl:template match="/netconf10:hello">
    <xsl:apply-templates select="netconf10:capabilities/netconf10:capability"/>
  </xsl:template>

  <xsl:template match="/netconf10:hello/netconf10:capabilities/netconf10:capability">
    <xsl:text></xsl:text><xsl:value-of select="text()"/><xsl:text>
</xsl:text>
  </xsl:template>
  
  <xsl:template match="*">
    <xsl:message terminate="yes">
      WARNING: Unmatched element: <xsl:value-of select="name()"/>
    </xsl:message>
    <xsl:apply-templates/>
  </xsl:template>
  <xsl:template match="text( )|@*"/>
</xsl:stylesheet>
